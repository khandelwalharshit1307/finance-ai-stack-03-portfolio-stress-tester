# scenario_builder.py
# Finance x AI — Module 04: Portfolio Stress Tester
# Scenario definitions — parameters, slider ranges, descriptions
# Author: Harshit Khandelwal

# ─────────────────────────────────────────────
# SCENARIO DEFINITIONS
# Each scenario has:
#   description  — one line shown in dashboard
#   params       — default parameter values
#   sliders      — (min, max, step) per adjustable param
# ─────────────────────────────────────────────

SCENARIOS = {

    "Rate Hike Shock": {
        "description": "Central bank overtightening — rates rise sharply, curve flattens, equities re-rate",
        "params": {
            "rate_hike_bps":      200,
            "ig_spread_widen":    60,
            "hy_spread_widen":    150,
            "equity_chg_pct":     -12.0,
            "oil_chg_pct":        0.0,
            "gdp_drop_pct":       -0.5,
            "em_stress_bps":      80,
        },
        "sliders": {
            "rate_hike_bps":      (0,    400,  25),
            "ig_spread_widen":    (0,    200,  10),
            "hy_spread_widen":    (0,    500,  25),
            "equity_chg_pct":     (-30,  10,   1),
            "em_stress_bps":      (0,    300,  25),
        },
        "analogs": ["2022 Rate Shock", "1994 Bond Massacre", "2018 Q4 Selloff"],
    },

    "Oil Price Shock": {
        "description": "Oil spikes 40%+ — inflation surge, growth drag, EM commodity exporters diverge",
        "params": {
            "rate_hike_bps":      80,
            "ig_spread_widen":    40,
            "hy_spread_widen":    200,
            "equity_chg_pct":     -8.0,
            "oil_chg_pct":        45.0,
            "gdp_drop_pct":       -1.0,
            "em_stress_bps":      120,
        },
        "sliders": {
            "oil_chg_pct":        (-70,  100,  5),
            "rate_hike_bps":      (0,    200,  25),
            "hy_spread_widen":    (0,    500,  25),
            "gdp_drop_pct":       (-4.0, 0.0,  0.5),
            "em_stress_bps":      (0,    300,  25),
        },
        "analogs": ["1973 OPEC Embargo", "2022 Russia-Ukraine Spike", "2014 Oil Crash"],
    },

    "Recession": {
        "description": "GDP contracts, unemployment spikes, credit cycle turns — defaults rise across HY and loans",
        "params": {
            "rate_hike_bps":      -100,
            "ig_spread_widen":    150,
            "hy_spread_widen":    400,
            "equity_chg_pct":     -25.0,
            "oil_chg_pct":        -20.0,
            "gdp_drop_pct":       -2.5,
            "em_stress_bps":      200,
        },
        "sliders": {
            "gdp_drop_pct":       (-8.0, 0.0,  0.5),
            "hy_spread_widen":    (0,    900,  50),
            "ig_spread_widen":    (0,    400,  25),
            "equity_chg_pct":     (-55,  0,    1),
            "em_stress_bps":      (0,    500,  25),
        },
        "analogs": ["2008 GFC", "2001 Dot-com / 9/11", "2020 COVID Crash"],
    },

    "Credit Crunch": {
        "description": "Liquidity freeze — spreads blow out, funding markets seize, forced selling amplifies losses",
        "params": {
            "rate_hike_bps":      0,
            "ig_spread_widen":    200,
            "hy_spread_widen":    600,
            "equity_chg_pct":     -20.0,
            "oil_chg_pct":        -15.0,
            "gdp_drop_pct":       -1.5,
            "em_stress_bps":      350,
        },
        "sliders": {
            "hy_spread_widen":    (0,    1500, 50),
            "ig_spread_widen":    (0,    500,  25),
            "equity_chg_pct":     (-55,  0,    1),
            "gdp_drop_pct":       (-5.0, 0.0,  0.5),
            "em_stress_bps":      (0,    600,  25),
        },
        "analogs": ["2008 GFC", "2011 EU Debt Crisis", "2020 COVID Crash"],
    },

    "EM Crisis": {
        "description": "EM selloff — USD strengthens, capital outflows, EM sovereign spreads widen sharply",
        "params": {
            "rate_hike_bps":      50,
            "ig_spread_widen":    30,
            "hy_spread_widen":    150,
            "equity_chg_pct":     -15.0,
            "oil_chg_pct":        -10.0,
            "gdp_drop_pct":       -1.0,
            "em_stress_bps":      400,
        },
        "sliders": {
            "em_stress_bps":      (0,    800,  25),
            "equity_chg_pct":     (-40,  0,    1),
            "hy_spread_widen":    (0,    400,  25),
            "gdp_drop_pct":       (-5.0, 0.0,  0.5),
            "rate_hike_bps":      (-100, 200,  25),
        },
        "analogs": ["2013 Taper Tantrum", "1997 Asian Crisis", "2018 EM Selloff"],
    },

    "Stagflation": {
        "description": "High inflation + low growth — central banks forced to hike into a slowdown",
        "params": {
            "rate_hike_bps":      150,
            "ig_spread_widen":    100,
            "hy_spread_widen":    300,
            "equity_chg_pct":     -18.0,
            "oil_chg_pct":        30.0,
            "gdp_drop_pct":       -1.5,
            "em_stress_bps":      200,
        },
        "sliders": {
            "rate_hike_bps":      (0,    400,  25),
            "gdp_drop_pct":       (-5.0, 0.0,  0.5),
            "oil_chg_pct":        (-20,  80,   5),
            "hy_spread_widen":    (0,    600,  25),
            "equity_chg_pct":     (-40,  0,    1),
        },
        "analogs": ["1970s OPEC + Fed Tightening", "2022 Rate Shock"],
    },

    "Custom": {
        "description": "Build your own scenario — full control over all parameters",
        "params": {
            "rate_hike_bps":      0,
            "ig_spread_widen":    0,
            "hy_spread_widen":    0,
            "equity_chg_pct":     0.0,
            "oil_chg_pct":        0.0,
            "gdp_drop_pct":       0.0,
            "em_stress_bps":      0,
        },
        "sliders": {
            "rate_hike_bps":      (-300, 500,  25),
            "ig_spread_widen":    (-50,  500,  10),
            "hy_spread_widen":    (-100, 1500, 25),
            "equity_chg_pct":     (-60,  30,   1),
            "oil_chg_pct":        (-70,  100,  5),
            "gdp_drop_pct":       (-8.0, 3.0,  0.5),
            "em_stress_bps":      (-50,  800,  25),
        },
        "analogs": [],
    },
}

# ─────────────────────────────────────────────
# PARAMETER DISPLAY LABELS
# Used by dashboard for slider labels
# ─────────────────────────────────────────────

PARAM_LABELS = {
    "rate_hike_bps":      "Rate change (bps)",
    "ig_spread_widen":    "IG spread change (bps)",
    "hy_spread_widen":    "HY spread change (bps)",
    "equity_chg_pct":     "Equity index change (%)",
    "oil_chg_pct":        "Oil price change (%)",
    "gdp_drop_pct":       "GDP impact (pp)",
    "em_stress_bps":      "EM spread stress (bps)",
}

# ─────────────────────────────────────────────
# PARAMETER DESCRIPTIONS
# Shown as tooltip / help text in dashboard
# ─────────────────────────────────────────────

PARAM_HELP = {
    "rate_hike_bps":   "Parallel shift in risk-free yield curve. Positive = rates rise.",
    "ig_spread_widen": "Change in investment grade option-adjusted spread (OAS).",
    "hy_spread_widen": "Change in high yield OAS. Drives HY bond and leveraged loan P&L.",
    "equity_chg_pct":  "Change in broad equity index (S&P 500 / Stoxx 50 proxy).",
    "oil_chg_pct":     "Change in crude oil price. Drives commodities and inflation.",
    "gdp_drop_pct":    "GDP growth impact in percentage points. Negative = contraction.",
    "em_stress_bps":   "EM sovereign spread widening. Captures EM-specific stress and FX.",
}


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Loaded {len(SCENARIOS)} scenarios:\n")
    for name, sc in SCENARIOS.items():
        print(f"  {name}")
        print(f"    {sc['description']}")
        print(f"    Sliders: {list(sc['sliders'].keys())}")
        if sc["analogs"]:
            print(f"    Analogs: {sc['analogs']}")
        print()