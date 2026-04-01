# dashboard.py
# Finance x AI — Module 04: Portfolio Stress Tester
# Author: Harshit Khandelwal

import os
import tempfile
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from data_loader import get_all_market_data
from bloomberg_parser import parse_bloomberg_export, aggregate_by_asset_class
from scenario_builder import SCENARIOS, PARAM_LABELS, PARAM_HELP
from risk_engine import (
    compute_asset_shocks,
    compute_portfolio_pnl,
    find_historical_analog,
    compute_correlation_matrix,
    compute_stressed_correlation,
)
from groq_narrator import generate_narrative, generate_hedge_suggestions

load_dotenv()

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Portfolio Stress Tester",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
    section[data-testid="stSidebar"] { width: 240px !important; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
    .stTabs [data-baseweb="tab"] { font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR — minimal, just data refresh
# ─────────────────────────────────────────────

with st.sidebar:
    st.caption("Finance × AI — Module 04")
    if st.button("🔄 Refresh market data", use_container_width=True):
        st.session_state.pop("market_data", None)
    if "market_data" not in st.session_state:
        with st.spinner("Loading..."):
            st.session_state.market_data = get_all_market_data()
    md   = st.session_state.market_data
    fred = md["fred"]
    yf   = md["yf"]
    st.caption(
        f"10Y: **{fred.get('us_10y','—')}%** · "
        f"VIX: **{yf.get('vix','—')}** · "
        f"HY OAS: **{round((fred.get('hy_oas') or 0)*100)}bp**"
    )

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

st.title("📉 Portfolio Stress Tester")
st.caption(
    f"Live data · US 10Y **{fred.get('us_10y','—')}%** · "
    f"IG OAS **{round((fred.get('ig_oas') or 0)*100)}bp** · "
    f"HY OAS **{round((fred.get('hy_oas') or 0)*100)}bp** · "
    f"VIX **{yf.get('vix','—')}** · "
    f"S&P **{yf.get('sp500','—')}** · "
    f"Brent **${yf.get('brent','—')}** · "
    f"CPI **{fred.get('cpi_yoy','—')}%** · "
    f"Unemp **{fred.get('unemployment','—')}%**"
)
st.divider()

# ─────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────

tab_stress, tab_portfolio, tab_corr, tab_about = st.tabs([
    "📊 Stress test",
    "🗂 Portfolio",
    "🔗 Correlations",
    "ℹ️ About",
])

# ══════════════════════════════════════════════
# TAB 1 — STRESS TEST
# ══════════════════════════════════════════════

with tab_stress:

    # ── ROW 1: Portfolio input + Scenario selector ──
    row1_left, row1_right = st.columns([1.2, 1.8], gap="large")

    with row1_left:
        st.subheader("Portfolio")
        input_mode = st.radio(
            "Input method",
            ["Manual weights", "Bloomberg export"],
            horizontal=True,
        )

        positions = None

        if input_mode == "Bloomberg export":
            upload = st.file_uploader(
                "Upload Bloomberg PORT .xlsx",
                type=["xlsx"],
                help="Bloomberg → PORT → Actions → Export → Excel"
            )
            if upload:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".xlsx"
                ) as tmp:
                    tmp.write(upload.read())
                    tmp_path = tmp.name
                try:
                    raw_df    = parse_bloomberg_export(tmp_path)
                    positions = aggregate_by_asset_class(raw_df)
                    st.success(
                        f"✅ {len(raw_df)} positions · "
                        f"{len(positions)} asset classes · "
                        f"Total: {positions['weight_pct'].sum():.1f}%"
                    )
                    os.unlink(tmp_path)
                except Exception as e:
                    st.error(f"Parse error: {e}")

        else:
            defaults = {
                "Gov bonds":       15,
                "IG credit":       20,
                "HY credit":       10,
                "Leveraged loans": 15,
                "Equities":        25,
                "EM debt":          5,
                "Commodities":      5,
                "Cash":             5,
            }
            alloc = {}
            cols_a, cols_b = st.columns(2)
            items = list(defaults.items())
            for i, (ac, default) in enumerate(items):
                col = cols_a if i % 2 == 0 else cols_b
                alloc[ac] = col.number_input(
                    ac,
                    min_value=0.0, max_value=100.0,
                    value=float(default), step=1.0,
                    key=f"alloc_{ac}",
                    label_visibility="visible",
                )
            total = sum(alloc.values())
            if abs(total - 100) > 0.5:
                st.warning(f"Total: {total:.1f}% — should be 100%")
            else:
                st.success(f"✅ Total: {total:.0f}%")

            positions = pd.DataFrame([
                {
                    "asset_class":     ac,
                    "weight_pct":      w,
                    "mod_duration":    None,
                    "spread_duration": None,
                    "beta":            None,
                    "oas_bps":         None,
                    "n_positions":     1,
                }
                for ac, w in alloc.items() if w > 0
            ])

    with row1_right:
        st.subheader("Scenario")
        scenario_name = st.selectbox(
            "Select scenario",
            list(SCENARIOS.keys()),
            label_visibility="collapsed",
        )
        sc = SCENARIOS[scenario_name]
        st.caption(sc["description"])
        if sc["analogs"]:
            st.caption(
                "Analogs: " + " · ".join(f"`{a}`" for a in sc["analogs"])
            )

        params = dict(sc["params"])
        sl1, sl2 = st.columns(2)
        slider_items = list(sc["sliders"].items())
        for i, (param_id, (lo, hi, step)) in enumerate(slider_items):
            col = sl1 if i % 2 == 0 else sl2
            label = PARAM_LABELS.get(param_id, param_id)
            help_text = PARAM_HELP.get(param_id, "")
            params[param_id] = col.slider(
                label,
                min_value=float(lo),
                max_value=float(hi),
                value=float(params[param_id]),
                step=float(step),
                help=help_text,
                key=f"sl_{param_id}",
            )

        run_btn = st.button(
            "▶ Run stress test",
            type="primary",
            use_container_width=True,
            disabled=(positions is None or positions.empty),
        )
        if positions is None or positions.empty:
            st.caption("⚠️ Add portfolio weights above to run")

    st.divider()

    # ── ROW 2: Results ──
    if run_btn and positions is not None and not positions.empty:
        with st.spinner("Computing shocks..."):
            shocks  = compute_asset_shocks(params, md, positions)
            pnl     = compute_portfolio_pnl(shocks, positions)
            analogs = find_historical_analog(params)
        st.session_state.last_results = {
            "shocks":        shocks,
            "pnl":           pnl,
            "analogs":       analogs,
            "scenario_name": scenario_name,
            "params":        params,
        }
        # clear old narrative on new run
        st.session_state.pop("narrative", None)
        st.session_state.pop("hedges", None)

    if "last_results" in st.session_state:
        r       = st.session_state.last_results
        pnl     = r["pnl"]
        shocks  = r["shocks"]
        analogs = r["analogs"]
        df      = pnl["positions_df"]
        total   = pnl["total_return"]

        # ── Metric cards ──
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Portfolio return",  f"{pnl['total_return']:+.2f}%")
        m2.metric("VaR (95%)",         f"{pnl['var_95']:+.2f}%")
        m3.metric("Max drawdown",      f"{pnl['max_drawdown']:+.2f}%")
        m4.metric("Vol estimate",      f"{pnl['vol_estimate']:.2f}%")
        m5.metric("Stress Sharpe",     f"{pnl['sharpe_stress']:.2f}")

        if total < -15:
            st.error("🔴 High risk — severe portfolio impact")
        elif total < -8:
            st.warning("🟡 Moderate risk — significant drawdown")
        else:
            st.success("🟢 Low risk — manageable impact")

        # ── Charts row ──
        ch1, ch2 = st.columns(2)

        with ch1:
            df_sorted = df.sort_values("contribution")
            colors = [
                "#E24B4A" if x < -1 else
                "#EF9F27" if x < 0 else
                "#639922"
                for x in df_sorted["contribution"]
            ]
            fig_w = go.Figure(go.Bar(
                x=df_sorted["asset_class"],
                y=df_sorted["contribution"],
                marker_color=colors,
                text=[f"{v:+.2f}%" for v in df_sorted["contribution"]],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Contribution: %{y:.2f}%<extra></extra>",
            ))
            fig_w.update_layout(
                title="P&L contribution by asset class (%)",
                height=320,
                margin=dict(t=40, b=20, l=0, r=0),
                yaxis_title="Contribution (%)",
                showlegend=False,
            )
            st.plotly_chart(fig_w, use_container_width=True)

        with ch2:
            shock_df = pd.DataFrame([
                {"Asset class": k, "Shock (%)": v}
                for k, v in shocks.items()
            ]).sort_values("Shock (%)")
            fig_s = px.bar(
                shock_df,
                x="Shock (%)", y="Asset class",
                orientation="h",
                color="Shock (%)",
                color_continuous_scale=["#E24B4A", "#EF9F27", "#639922"],
                title="Asset class shock (%)",
                text="Shock (%)",
            )
            fig_s.update_traces(
                texttemplate="%{text:+.1f}%",
                textposition="outside"
            )
            fig_s.update_layout(
                height=320,
                margin=dict(t=40, b=20, l=0, r=0),
                showlegend=False,
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_s, use_container_width=True)

        # ── Breakdown table ──
        with st.expander("Full breakdown table"):
            display_df = df[[
                "asset_class", "weight_pct", "shock_pct", "contribution"
            ]].copy()
            display_df.columns = [
                "Asset class", "Weight (%)", "Shock (%)", "Contribution (%)"
            ]
            st.dataframe(
                display_df.style.format({
                    "Weight (%)":       "{:.1f}",
                    "Shock (%)":        "{:+.2f}",
                    "Contribution (%)": "{:+.3f}",
                }).background_gradient(
                    subset=["Contribution (%)"],
                    cmap="RdYlGn",
                    vmin=-5, vmax=2
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()

        # ── AI section ──
        st.subheader("AI analysis")
        st.caption(
            f"Scenario: **{r['scenario_name']}** · "
            f"Closest analogs: " +
            " · ".join(f"**{a}**" for a in analogs)
        )

        ai_col1, ai_col2 = st.columns(2)

        with ai_col1:
            if st.button(
                "🤖 Generate narrative",
                use_container_width=True,
                key="btn_narrative"
            ):
                with st.spinner("Groq llama-3.3-70b thinking..."):
                    st.session_state.narrative = generate_narrative(
                        r["scenario_name"],
                        r["params"],
                        pnl,
                        analogs,
                        md,
                    )
            if "narrative" in st.session_state:
                st.info(st.session_state.narrative)

        with ai_col2:
            if st.button(
                "🛡 Suggest hedges",
                use_container_width=True,
                key="btn_hedges"
            ):
                with st.spinner("Generating hedge recommendations..."):
                    st.session_state.hedges = generate_hedge_suggestions(
                        r["scenario_name"],
                        r["params"],
                        pnl,
                        md,
                    )
            if "hedges" in st.session_state:
                st.success(st.session_state.hedges)

    else:
        st.info(
            "Configure portfolio and scenario above, "
            "then click **▶ Run stress test**."
        )

# ══════════════════════════════════════════════
# TAB 2 — PORTFOLIO
# ══════════════════════════════════════════════

with tab_portfolio:
    try:
        if positions is not None and not positions.empty:
            st.subheader("Portfolio composition")
            p1, p2 = st.columns([1, 1])

            with p1:
                fig_pie = px.pie(
                    positions,
                    names="asset_class",
                    values="weight_pct",
                    title="Allocation by asset class",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig_pie.update_layout(
                    height=360, margin=dict(t=40, b=0, l=0, r=0)
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with p2:
                st.markdown("**Position detail**")
                show_cols = ["asset_class", "weight_pct"]
                for c in ["mod_duration", "spread_duration",
                           "oas_bps", "beta", "n_positions"]:
                    if c in positions.columns and positions[c].notna().any():
                        show_cols.append(c)
                label_map = {
                    "asset_class":     "Asset class",
                    "weight_pct":      "Weight (%)",
                    "mod_duration":    "Mod duration",
                    "spread_duration": "Spread dur",
                    "oas_bps":         "OAS (bps)",
                    "beta":            "Beta",
                    "n_positions":     "# Positions",
                }
                display = positions[show_cols].copy()
                display.rename(columns=label_map, inplace=True)
                st.dataframe(
                    display.style.format(precision=2, na_rep="—"),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("Add portfolio weights in the Stress test tab.")
    except Exception:
        st.info("Run a stress test first to see portfolio composition.")

# ══════════════════════════════════════════════
# TAB 3 — CORRELATIONS
# ══════════════════════════════════════════════

with tab_corr:
    st.subheader("Cross-asset correlation — 2Y rolling daily returns")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Normal conditions**")
        corr_n = compute_correlation_matrix(md["returns"])
        if not corr_n.empty:
            fig_cn = px.imshow(
                corr_n,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdYlGn",
                zmin=-1, zmax=1,
                title="All market conditions",
            )
            fig_cn.update_layout(
                height=440, margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_cn, use_container_width=True)

    with c2:
        st.markdown("**Stress regime (worst 10% equity days)**")
        corr_s = compute_stressed_correlation(md["returns"])
        if not corr_s.empty:
            fig_cs = px.imshow(
                corr_s,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdYlGn",
                zmin=-1, zmax=1,
                title="Stress regime only",
            )
            fig_cs.update_layout(
                height=440, margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_cs, use_container_width=True)
        else:
            st.info("Not enough stressed days to compute.")

    st.divider()
    st.caption(
        "Key insight: gov bonds (TLT) show negative correlation with equities "
        "in normal conditions — the classic diversifier. In stress regimes this "
        "breaks down. HY credit and leveraged loans spike toward equity correlation "
        "in crises — the non-linear risk that static models miss."
    )

# ══════════════════════════════════════════════
# TAB 4 — ABOUT
# ══════════════════════════════════════════════

with tab_about:
    st.subheader("Portfolio Stress Tester — Finance × AI Module 04")
    st.markdown("""
**What it does**

Stress tests a multi-asset portfolio across 7 macro scenarios using live
market data from FRED and yfinance. AI narrative explains the transmission
mechanism, identifies the most exposed positions, and recommends specific hedges.

---

**Data sources**

| Source | Coverage | Used for |
|---|---|---|
| FRED | 30+ series — yields, spreads, macro | Shock calibration, live anchors |
| yfinance | 35+ tickers — equities, commodities, FX, ETFs | Beta, correlation, live prices |
| Bloomberg PORT | Position-level .xlsx export | Actual duration, spread duration, beta |

---

**Risk engine**

- Modified duration × rate shock → gov bonds, IG credit
- Spread duration × spread widening → IG, HY, loans, EM
- Floating rate benefit → leveraged loans (SOFR-linked)
- Beta × equity move + P/E compression → equities
- VIX multiplier → amplifies credit and EM shocks in high-vol regimes
- Historical analog matching → normalised Euclidean distance, 8 episodes

---

**AI layer**

Groq `llama-3.3-70b-versatile` — scenario narrative + hedge suggestions
conditioned on exact portfolio mix, live market levels, and stress output.
Cost: $0.

---

**Stack**

`Python` · `Streamlit` · `Plotly` · `FRED API` · `yfinance` · `Groq` · `pandas` · `numpy`
    """)
    st.divider()
    st.caption(
        "Built by **Harshit Khandelwal** | "
        "Leveraged Loans Analyst @ BNP Paribas AM | "
        "ESSEC MiM 2026 | "
        "https://www.linkedin.com/in/harshit-khandelwal-6278a4193/"
        "https://github.com/khandelwalharshit1307/finance-ai-stack-03-portfolio-stress-tester"
    )
