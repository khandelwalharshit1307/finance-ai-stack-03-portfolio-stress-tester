# groq_narrator.py
# Finance x AI — Module 04: Portfolio Stress Tester
# AI narrative engine — Groq llama-3.3-70b generates scenario commentary
# Author: Harshit Khandelwal

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior portfolio risk analyst at a major asset manager.
You write concise, practitioner-level stress test commentary for portfolio managers.
Rules:
- Be specific about transmission mechanisms — name the exact channel (duration, spread widening, beta, FX)
- Reference actual numbers from the data provided
- Mention second-order effects: liquidity, forced selling, margin calls, correlation breakdown
- Suggest one concrete hedging instrument (name it specifically — CDX HY, TLT puts, USD long, etc.)
- Tone: direct, no fluff, written for someone who manages money
- Format: 4 short paragraphs, no bullet points, no headers, no markdown
- Length: 180-220 words total"""


# ─────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────

def build_prompt(
    scenario_name: str,
    scenario_params: dict,
    pnl_results: dict,
    historical_analogs: list,
    market_data: dict,
) -> str:
    """
    Build the full user prompt from stress test results.
    Passes live market levels so AI commentary is anchored
    to current conditions, not generic.
    """
    df = pnl_results["positions_df"]

    # Top 3 worst contributors
    worst = (df.sort_values("contribution")
               .head(3)[["asset_class", "weight_pct", "shock_pct", "contribution"]]
               .to_string(index=False))

    # Top 1 best contributor
    best = (df.sort_values("contribution", ascending=False)
              .head(1)[["asset_class", "weight_pct", "shock_pct", "contribution"]]
              .to_string(index=False))

    # Live market context
    fred = market_data.get("fred", {})
    yf   = market_data.get("yf", {})

    us_10y   = fred.get("us_10y", "N/A")
    ig_oas   = round((fred.get("ig_oas") or 0) * 100, 0)
    hy_oas   = round((fred.get("hy_oas") or 0) * 100, 0)
    vix      = yf.get("vix", "N/A")
    sp500    = yf.get("sp500", "N/A")

    # Scenario parameter summary
    param_lines = "\n".join([
        f"  Rate change:         {scenario_params.get('rate_hike_bps', 0):+.0f} bps",
        f"  IG spread change:    {scenario_params.get('ig_spread_widen', 0):+.0f} bps",
        f"  HY spread change:    {scenario_params.get('hy_spread_widen', 0):+.0f} bps",
        f"  Equity change:       {scenario_params.get('equity_chg_pct', 0):+.1f}%",
        f"  Oil change:          {scenario_params.get('oil_chg_pct', 0):+.1f}%",
        f"  GDP impact:          {scenario_params.get('gdp_drop_pct', 0):+.1f} pp",
        f"  EM stress:           {scenario_params.get('em_stress_bps', 0):+.0f} bps",
    ])

    prompt = f"""
SCENARIO: {scenario_name}
CLOSEST HISTORICAL ANALOGS: {', '.join(historical_analogs)}

CURRENT MARKET LEVELS:
  US 10Y yield: {us_10y}%
  IG OAS: {ig_oas} bps
  HY OAS: {hy_oas} bps
  VIX: {vix}
  S&P 500: {sp500}

SCENARIO PARAMETERS:
{param_lines}

PORTFOLIO RESULTS:
  Total return:   {pnl_results['total_return']:+.2f}%
  VaR (95%):      {pnl_results['var_95']:+.2f}%
  Max drawdown:   {pnl_results['max_drawdown']:+.2f}%
  Stress Sharpe:  {pnl_results['sharpe_stress']:.2f}

WORST CONTRIBUTORS:
{worst}

BEST CONTRIBUTOR:
{best}

Write the stress test commentary now. 4 paragraphs:
1) Primary transmission mechanism driving the loss
2) Why the worst positions are specifically exposed — use the actual shock numbers
3) Second-order and non-linear risks in this scenario
4) One specific hedge recommendation with the instrument name
"""
    return prompt.strip()


# ─────────────────────────────────────────────
# MAIN NARRATOR
# ─────────────────────────────────────────────

def generate_narrative(
    scenario_name: str,
    scenario_params: dict,
    pnl_results: dict,
    historical_analogs: list,
    market_data: dict,
) -> str:
    """
    Generate AI narrative for stress test results via Groq.
    Returns plain text — 4 paragraphs, ~200 words.
    """
    prompt = build_prompt(
        scenario_name,
        scenario_params,
        pnl_results,
        historical_analogs,
        market_data,
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.35,   # low temp = consistent, factual tone
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return (
            f"Narrative unavailable: {e}\n\n"
            f"Quantitative results are valid — portfolio return "
            f"{pnl_results['total_return']:+.2f}%, "
            f"VaR {pnl_results['var_95']:+.2f}%."
        )


# ─────────────────────────────────────────────
# HEDGE SUGGESTER — standalone call
# ─────────────────────────────────────────────

def generate_hedge_suggestions(
    scenario_name: str,
    scenario_params: dict,
    pnl_results: dict,
    market_data: dict,
) -> str:
    """
    Separate focused call — returns 3 specific hedge ideas
    with instrument, rationale, and sizing logic.
    Called from dashboard when user clicks 'Suggest hedges'.
    """
    df = pnl_results["positions_df"]
    worst = (df.sort_values("contribution")
               .head(3)[["asset_class", "shock_pct", "contribution"]]
               .to_string(index=False))

    prompt = f"""
Scenario: {scenario_name}
Portfolio total return under stress: {pnl_results['total_return']:+.2f}%
Worst positions:
{worst}

Suggest exactly 3 hedges. For each:
- Name the specific instrument (e.g. CDX HY 5Y, TLT puts, short EUR/USD, long VIX calls)
- One sentence on why it hedges this specific scenario
- Approximate notional sizing as % of portfolio (e.g. 2-3% of NAV)

Be specific. No generic advice. Write for a portfolio manager who will execute tomorrow.
Format: numbered list, 3 items, 2-3 sentences each.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a senior derivatives and risk overlay specialist at a major asset manager. Give specific, actionable hedge recommendations."},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Hedge suggestions unavailable: {e}"


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd
    from data_loader import get_all_market_data
    from risk_engine import (
        compute_asset_shocks,
        compute_portfolio_pnl,
        find_historical_analog,
    )

    print("Loading market data...")
    md = get_all_market_data()

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

    scenario_name = "Rate Hike Shock"
    scenario_params = {
        "rate_hike_bps":    200,
        "ig_spread_widen":  60,
        "hy_spread_widen":  200,
        "equity_chg_pct":   -12,
        "oil_chg_pct":      0,
        "gdp_drop_pct":     -0.5,
        "em_stress_bps":    80,
    }

    print("Computing risk engine...")
    shocks  = compute_asset_shocks(scenario_params, md, default_positions)
    pnl     = compute_portfolio_pnl(shocks, default_positions)
    analogs = find_historical_analog(scenario_params)

    print("\nGenerating AI narrative...")
    print("─" * 60)
    narrative = generate_narrative(
        scenario_name, scenario_params, pnl, analogs, md
    )
    print(narrative)

    print("\n" + "─" * 60)
    print("Generating hedge suggestions...")
    print("─" * 60)
    hedges = generate_hedge_suggestions(
        scenario_name, scenario_params, pnl, md
    )
    print(hedges)