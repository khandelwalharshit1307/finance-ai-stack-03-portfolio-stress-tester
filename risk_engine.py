# risk_engine.py
# Finance x AI — Module 04: Portfolio Stress Tester
# Core quant engine — shock transmission, P&L, risk metrics, historical analogs
# Author: Harshit Khandelwal

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# HISTORICAL SCENARIO DATABASE
# Realized market moves during major episodes
# Used for analog matching via Euclidean distance
# ─────────────────────────────────────────────

HISTORICAL_SCENARIOS = {
    "2022 Rate Shock": {
        "rate_hike_bps":      425,
        "ig_spread_widen":    80,
        "hy_spread_widen":    280,
        "equity_chg_pct":     -19,
        "oil_chg_pct":        6,
        "gdp_drop_pct":       -0.6,
        "em_stress_bps":      150,
    },
    "2020 COVID Crash": {
        "rate_hike_bps":      -150,
        "ig_spread_widen":    180,
        "hy_spread_widen":    650,
        "equity_chg_pct":     -34,
        "oil_chg_pct":        -67,
        "gdp_drop_pct":       -3.4,
        "em_stress_bps":      300,
    },
    "2008 GFC": {
        "rate_hike_bps":      -300,
        "ig_spread_widen":    350,
        "hy_spread_widen":    1900,
        "equity_chg_pct":     -57,
        "oil_chg_pct":        -75,
        "gdp_drop_pct":       -4.3,
        "em_stress_bps":      600,
    },
    "2011 EU Debt Crisis": {
        "rate_hike_bps":      50,
        "ig_spread_widen":    120,
        "hy_spread_widen":    400,
        "equity_chg_pct":     -21,
        "oil_chg_pct":        -10,
        "gdp_drop_pct":       -0.8,
        "em_stress_bps":      200,
    },
    "2018 Q4 Selloff": {
        "rate_hike_bps":      100,
        "ig_spread_widen":    55,
        "hy_spread_widen":    200,
        "equity_chg_pct":     -20,
        "oil_chg_pct":        -40,
        "gdp_drop_pct":       0.0,
        "em_stress_bps":      100,
    },
    "2013 Taper Tantrum": {
        "rate_hike_bps":      130,
        "ig_spread_widen":    40,
        "hy_spread_widen":    120,
        "equity_chg_pct":     -6,
        "oil_chg_pct":        -5,
        "gdp_drop_pct":       0.0,
        "em_stress_bps":      180,
    },
    "2001 Dot-com / 9/11": {
        "rate_hike_bps":      -475,
        "ig_spread_widen":    180,
        "hy_spread_widen":    700,
        "equity_chg_pct":     -49,
        "oil_chg_pct":        -30,
        "gdp_drop_pct":       -0.4,
        "em_stress_bps":      250,
    },
    "1994 Bond Massacre": {
        "rate_hike_bps":      300,
        "ig_spread_widen":    60,
        "hy_spread_widen":    180,
        "equity_chg_pct":     -8,
        "oil_chg_pct":        0,
        "gdp_drop_pct":       0.0,
        "em_stress_bps":      400,
    },
}

# ─────────────────────────────────────────────
# DEFAULT DURATION / SENSITIVITY ASSUMPTIONS
# Used when Bloomberg data is not available
# ─────────────────────────────────────────────

DEFAULT_DURATIONS = {
    "Gov bonds":        7.5,    # ~10Y Treasury modified duration
    "IG credit":        6.2,    # typical IG bond duration
    "HY credit":        3.8,    # shorter duration, more spread-driven
    "Leveraged loans":  0.25,   # floating rate — minimal duration
    "Equities":         0.0,    # not duration-driven
    "EM debt":          6.5,    # USD EM sovereign
    "Commodities":      0.0,
    "Cash":             0.08,   # overnight, near zero duration
}

DEFAULT_SPREAD_DURATIONS = {
    "Gov bonds":        0.0,
    "IG credit":        5.8,
    "HY credit":        3.5,
    "Leveraged loans":  2.2,    # spread duration despite floating rate
    "Equities":         0.0,
    "EM debt":          6.0,
    "Commodities":      0.0,
    "Cash":             0.0,
}

DEFAULT_EQUITY_BETA = {
    "Gov bonds":        -0.15,  # slight negative beta (flight to quality)
    "IG credit":        0.25,
    "HY credit":        0.55,
    "Leveraged loans":  0.40,
    "Equities":         1.0,
    "EM debt":          0.45,
    "Commodities":      0.30,
    "Cash":             0.0,
}


# ─────────────────────────────────────────────
# CORE SHOCK ENGINE
# ─────────────────────────────────────────────

def compute_asset_shocks(
    scenario_params: dict,
    market_data: dict,
    positions: pd.DataFrame = None
) -> dict:
    """
    Compute % P&L shock per asset class.

    Transmission logic:
      - Rate shock   → duration × DV01 loss
      - Spread shock → spread duration × spread widening
      - Equity shock → beta × equity move + growth drag
      - Leveraged loans → floating rate benefit partially offsets spread loss
      - EM → rate + spread + implicit FX stress
      - Commodities → oil-driven + growth correlation

    Uses live FRED data to anchor current spread/yield levels.
    Falls back to defaults if market_data is incomplete.

    Returns dict of {asset_class: shock_%}
    """
    p = scenario_params
    fred = market_data.get("fred", {})

    # ── Live market anchors ──
    us_10y   = fred.get("us_10y")   or 4.35
    ig_oas   = (fred.get("ig_oas")  or 0.90) * 100   # convert to bps
    hy_oas   = (fred.get("hy_oas")  or 3.28) * 100   # convert to bps
    sofr     = fred.get("sofr")     or 5.30
    vix      = market_data.get("yf", {}).get("vix") or 20

    # ── Scenario parameters (with defaults) ──
    rate_shock_bps  = p.get("rate_hike_bps",      0)
    ig_widen_bps    = p.get("ig_spread_widen",     0)
    hy_widen_bps    = p.get("hy_spread_widen",     0)
    eq_chg_pct      = p.get("equity_chg_pct",      0)
    oil_chg_pct     = p.get("oil_chg_pct",         0)
    gdp_drop_pp     = p.get("gdp_drop_pct",        0)
    em_stress_bps   = p.get("em_stress_bps",       0)

    # Convert bps → decimal for duration math
    rate_shock_pct  = rate_shock_bps  / 100
    ig_widen_pct    = ig_widen_bps    / 100
    hy_widen_pct    = hy_widen_bps    / 100
    em_stress_pct   = em_stress_bps   / 100

    # ── Resolve durations ──
    # If Bloomberg positions passed in, use weighted avg actuals
    # Otherwise fall back to defaults
    def get_duration(ac):
        if positions is not None and "mod_duration" in positions.columns:
            row = positions[positions["asset_class"] == ac]
            if not row.empty and pd.notna(row.iloc[0]["mod_duration"]):
                return float(row.iloc[0]["mod_duration"])
        return DEFAULT_DURATIONS.get(ac, 0)

    def get_spread_dur(ac):
        if positions is not None and "spread_duration" in positions.columns:
            row = positions[positions["asset_class"] == ac]
            if not row.empty and pd.notna(row.iloc[0]["spread_duration"]):
                return float(row.iloc[0]["spread_duration"])
        return DEFAULT_SPREAD_DURATIONS.get(ac, 0)

    def get_beta(ac):
        if positions is not None and "beta" in positions.columns:
            row = positions[positions["asset_class"] == ac]
            if not row.empty and pd.notna(row.iloc[0]["beta"]):
                return float(row.iloc[0]["beta"])
        return DEFAULT_EQUITY_BETA.get(ac, 0)

    # ── Volatility multiplier ──
    # High VIX environment amplifies credit and EM shocks
    vix_mult = 1.0 + max(0, (vix - 20) / 60)

    # ─────────────────────────────────────────────
    # SHOCK CALCULATIONS PER ASSET CLASS
    # P&L ≈ -Duration × ΔRate  -  SpreadDur × ΔSpread  +  Beta × ΔEquity
    # ─────────────────────────────────────────────

    shocks = {}

    # GOV BONDS — pure rate duration
    dur = get_duration("Gov bonds")
    shocks["Gov bonds"] = -(dur * rate_shock_pct)

    # IG CREDIT — rate duration + spread duration
    dur  = get_duration("IG credit")
    sdur = get_spread_dur("IG credit")
    shocks["IG credit"] = (
        -(dur  * rate_shock_pct)
        -(sdur * ig_widen_pct * vix_mult)
        -(abs(gdp_drop_pp) * 0.3)           # mild default premium
    )

    # HY CREDIT — less rate sensitivity, more spread + growth
    dur  = get_duration("HY credit")
    sdur = get_spread_dur("HY credit")
    shocks["HY credit"] = (
        -(dur  * rate_shock_pct)
        -(sdur * hy_widen_pct * vix_mult)
        -(abs(gdp_drop_pp) * 1.2)           # default risk rises with GDP fall
        +(get_beta("HY credit") * eq_chg_pct * 0.15)
    )

    # LEVERAGED LOANS — floating rate (SOFR-linked), so rate hike partially helps
    # But spread duration and default risk are the main drivers
    sdur = get_spread_dur("Leveraged loans")
    loan_rate_benefit = max(0, rate_shock_pct * 0.5)  # SOFR floor benefit
    shocks["Leveraged loans"] = (
        +loan_rate_benefit
        -(sdur * hy_widen_pct * 0.75 * vix_mult)   # loans less liquid than bonds
        -(abs(gdp_drop_pp) * 1.0)
    )

    # EQUITIES — beta-driven + P/E compression from rates + earnings from GDP
    beta = get_beta("Equities")
    pe_compression = -(rate_shock_pct * 2.5)         # higher rates = lower multiples
    earnings_impact = gdp_drop_pp * 1.5              # GDP fall hits earnings
    shocks["Equities"] = (
        (beta * eq_chg_pct)
        + pe_compression
        + earnings_impact
    )

    # EM DEBT — rate + EM-specific spread + implicit FX (USD strengthens in stress)
    dur  = get_duration("EM debt")
    sdur = get_spread_dur("EM debt")
    fx_drag = -(rate_shock_pct * 1.5)                # USD strengthens on rate hikes
    shocks["EM debt"] = (
        -(dur  * rate_shock_pct)
        -(sdur * em_stress_pct * vix_mult)
        + fx_drag
        -(abs(gdp_drop_pp) * 1.5)
    )

    # COMMODITIES — oil-driven + growth correlation + USD inverse
    oil_component   = oil_chg_pct * 0.55
    growth_drag     = gdp_drop_pp * 0.9
    usd_drag        = -(rate_shock_pct * 1.2)        # stronger USD = lower commodities
    shocks["Commodities"] = oil_component + growth_drag + usd_drag

    # CASH — SOFR/rate linked, always positive in rate hike
    shocks["Cash"] = max(0.0, rate_shock_pct * 0.7)

    return {k: round(v, 3) for k, v in shocks.items()}


# ─────────────────────────────────────────────
# PORTFOLIO P&L AGGREGATION
# ─────────────────────────────────────────────

def compute_portfolio_pnl(
    asset_shocks: dict,
    positions: pd.DataFrame,
) -> dict:
    """
    Aggregate asset-level shocks into portfolio P&L.

    For each position:
      contribution = weight% × shock%

    Returns total return, VaR, max drawdown, vol estimate,
    and a full breakdown DataFrame.
    """
    rows = []

    for _, pos in positions.iterrows():
        ac     = pos["asset_class"]
        weight = pos["weight_pct"]
        shock  = asset_shocks.get(ac, 0.0)
        contrib = round((weight / 100) * shock, 4)

        rows.append({
            "asset_class":   ac,
            "weight_pct":    round(weight, 2),
            "shock_pct":     shock,
            "contribution":  contrib,
            "n_positions":   int(pos.get("n_positions", 1)),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return {
            "positions_df":  df,
            "total_return":  0.0,
            "var_95":        0.0,
            "max_drawdown":  0.0,
            "vol_estimate":  0.0,
            "sharpe_stress": 0.0,
        }

    total_return = round(df["contribution"].sum(), 3)

    # ── Risk metrics ──
    # Parametric VaR: assumes shocks are roughly 1.65σ events
    var_95       = round(total_return * 1.65, 2)

    # Max drawdown proxy: stress return × severity multiplier
    max_drawdown = round(total_return * 1.40, 2)

    # Vol estimate: annualised, derived from stress magnitude
    vol_estimate = round(abs(total_return) * 0.38 + 1.5, 2)

    # Stress Sharpe: return per unit of estimated vol
    sharpe_stress = round(
        total_return / vol_estimate if vol_estimate != 0 else 0, 2
    )

    return {
        "positions_df":  df,
        "total_return":  total_return,
        "var_95":        var_95,
        "max_drawdown":  max_drawdown,
        "vol_estimate":  vol_estimate,
        "sharpe_stress": sharpe_stress,
    }


# ─────────────────────────────────────────────
# HISTORICAL ANALOG MATCHING
# ─────────────────────────────────────────────

def find_historical_analog(scenario_params: dict, top_n: int = 2) -> list:
    """
    Find the closest historical episodes to the current scenario
    using normalised Euclidean distance across shock dimensions.

    Returns list of episode names ranked by similarity.
    """
    keys = [
        "rate_hike_bps",
        "ig_spread_widen",
        "hy_spread_widen",
        "equity_chg_pct",
        "oil_chg_pct",
        "gdp_drop_pct",
        "em_stress_bps",
    ]

    user_vec = np.array(
        [scenario_params.get(k, 0) for k in keys], dtype=float
    )
    user_norm = np.linalg.norm(user_vec)
    user_vec_n = user_vec / user_norm if user_norm > 0 else user_vec

    distances = {}
    for name, hist in HISTORICAL_SCENARIOS.items():
        hist_vec = np.array([hist.get(k, 0) for k in keys], dtype=float)
        hist_norm = np.linalg.norm(hist_vec)
        hist_vec_n = hist_vec / hist_norm if hist_norm > 0 else hist_vec
        distances[name] = round(
            float(np.linalg.norm(user_vec_n - hist_vec_n)), 4
        )

    ranked = sorted(distances.items(), key=lambda x: x[1])
    return [name for name, _ in ranked[:top_n]]


# ─────────────────────────────────────────────
# CORRELATION MATRIX
# ─────────────────────────────────────────────

def compute_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build cross-asset correlation matrix from 2Y daily returns.

    Uses liquid ETF proxies for each asset class:
      sp500 = equities, tlt = rates, lqd = IG, hyg = HY,
      bkln = loans, emb = EM debt, gold = safe haven,
      brent = commodities, dxy = USD
    """
    proxy_cols = [
        "sp500", "tlt", "lqd", "hyg", "bkln",
        "emb", "em_equity", "gold", "brent", "dxy"
    ]
    available = [c for c in proxy_cols if c in returns_df.columns]

    if len(available) < 2:
        return pd.DataFrame()

    corr = returns_df[available].corr().round(3)

    # Rename to readable labels
    label_map = {
        "sp500":      "Equities (SPX)",
        "tlt":        "Gov bonds (TLT)",
        "lqd":        "IG credit (LQD)",
        "hyg":        "HY credit (HYG)",
        "bkln":       "Lev loans (BKLN)",
        "emb":        "EM debt (EMB)",
        "em_equity":  "EM equity (EEM)",
        "gold":       "Gold",
        "brent":      "Brent crude",
        "dxy":        "USD (DXY)",
    }
    corr.rename(index=label_map, columns=label_map, inplace=True)

    return corr


# ─────────────────────────────────────────────
# STRESSED CORRELATION
# ─────────────────────────────────────────────

def compute_stressed_correlation(
    returns_df: pd.DataFrame,
    stress_percentile: float = 0.10
) -> pd.DataFrame:
    """
    Compute correlation matrix using only the worst
    stress_percentile of days (bottom 10% equity return days).

    Shows how correlations spike toward 1 in a crisis —
    the key non-linear risk in multi-asset portfolios.
    """
    if "sp500" not in returns_df.columns:
        return pd.DataFrame()

    threshold = returns_df["sp500"].quantile(stress_percentile)
    stress_days = returns_df[returns_df["sp500"] <= threshold]

    if len(stress_days) < 10:
        return pd.DataFrame()

    proxy_cols = [
        "sp500", "tlt", "lqd", "hyg", "bkln",
        "emb", "gold", "brent", "dxy"
    ]
    available = [c for c in proxy_cols if c in stress_days.columns]
    corr = stress_days[available].corr().round(3)

    label_map = {
        "sp500": "Equities", "tlt": "Gov bonds", "lqd": "IG credit",
        "hyg": "HY credit", "bkln": "Lev loans", "emb": "EM debt",
        "gold": "Gold", "brent": "Brent", "dxy": "USD",
    }
    corr.rename(index=label_map, columns=label_map, inplace=True)
    return corr


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from data_loader import get_all_market_data

    print("Loading market data...")
    md = get_all_market_data()

    # Test with default portfolio (no Bloomberg file)
    default_positions = pd.DataFrame([
        {"asset_class": "Gov bonds",       "weight_pct": 15, "n_positions": 1},
        {"asset_class": "IG credit",       "weight_pct": 20, "n_positions": 1},
        {"asset_class": "HY credit",       "weight_pct": 10, "n_positions": 1},
        {"asset_class": "Leveraged loans", "weight_pct": 15, "n_positions": 1},
        {"asset_class": "Equities",        "weight_pct": 25, "n_positions": 1},
        {"asset_class": "EM debt",         "weight_pct":  5, "n_positions": 1},
        {"asset_class": "Commodities",     "weight_pct":  5, "n_positions": 1},
        {"asset_class": "Cash",            "weight_pct":  5, "n_positions": 1},
    ])

    # Rate hike scenario
    scenario = {
        "rate_hike_bps":    200,
        "ig_spread_widen":  60,
        "hy_spread_widen":  200,
        "equity_chg_pct":   -12,
        "oil_chg_pct":      0,
        "gdp_drop_pct":     -0.5,
        "em_stress_bps":    80,
    }

    print("\nComputing shocks...")
    shocks = compute_asset_shocks(scenario, md, default_positions)
    print("\n── Asset shocks ──")
    for ac, shock in shocks.items():
        print(f"  {ac:22s}: {shock:+.2f}%")

    print("\nComputing portfolio P&L...")
    pnl = compute_portfolio_pnl(shocks, default_positions)
    print(f"\n── Portfolio results ──")
    print(f"  Total return   : {pnl['total_return']:+.2f}%")
    print(f"  VaR (95%)      : {pnl['var_95']:+.2f}%")
    print(f"  Max drawdown   : {pnl['max_drawdown']:+.2f}%")
    print(f"  Vol estimate   : {pnl['vol_estimate']:.2f}%")
    print(f"  Stress Sharpe  : {pnl['sharpe_stress']:.2f}")

    print("\n── Contribution breakdown ──")
    print(pnl["positions_df"][
        ["asset_class", "weight_pct", "shock_pct", "contribution"]
    ].to_string(index=False))

    print("\nFinding historical analogs...")
    analogs = find_historical_analog(scenario)
    print(f"  Closest analogs: {analogs}")

    print("\nComputing correlation matrix...")
    corr = compute_correlation_matrix(md["returns"])
    print(f"  Matrix shape: {corr.shape}")
    print(corr)

    print("\nComputing stressed correlation (worst 10% equity days)...")
    stressed_corr = compute_stressed_correlation(md["returns"])
    if not stressed_corr.empty:
        print(stressed_corr)