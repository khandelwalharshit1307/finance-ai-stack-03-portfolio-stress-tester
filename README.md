# 📉 Portfolio Stress Tester — Finance × AI Module 04

An AI-powered portfolio stress testing tool built on live market data.
Pick a macro scenario, set the severity, and get a full portfolio impact
breakdown with AI-generated narrative — in seconds, for free.

Built by [Harshit Khandelwal](https://www.linkedin.com/in/harshit-khandelwal-6278a4193/) |
Leveraged Loans Analyst @ BNP Paribas AM | ESSEC MiM 2026

---

## What it does

You define a macro scenario — a rate hike, an oil shock, a recession, or
the current Iran war — and the tool computes what it does to each asset
class in your portfolio using real risk math. Then an AI explains why,
which positions are most exposed, and what hedge to consider.

Everything runs on free APIs. No Bloomberg terminal required to run it,
though you can plug one in if you have access.



**Iran war stress test — Oil +40%, HY spreads +200bps, EM stress +300bps:**

| Asset class | Weight | Shock | Contribution |
|---|---|---|---|
| Gov bonds | 20% | -3.75% | -0.75% |
| IG credit | 20% | -5.89% | -1.18% |
| HY credit | 15% | -11.28% | -1.69% |
| Leveraged loans | 15% | -4.30% | -0.64% |
| Equities | 15% | -10.75% | -1.61% |
| EM debt | 10% | -24.85% | -2.49% |
| Commodities | 5% | +20.50% | +1.03% |
| **Portfolio total** | | | **-7.34%** |

Commodities — the only green bar. EM debt — the biggest hit.
Leveraged loans outperformed HY by 7pp. Floating rate protection working
exactly as theory says.

---

## How it works
```
FRED + yfinance          Risk engine           Groq AI
(live market data)  →   (shock × duration) →  (narrative + hedges)
                              ↓
                        Streamlit dashboard
```

**Step 1 — Data pull**
On every run, the tool fetches live data: US yield curve (2Y/5Y/10Y/30Y),
IG and HY option-adjusted spreads, SOFR, VIX, oil, FX, and 35+ asset
price series. Shocks are anchored to today's market levels, not last
quarter's static table.

**Step 2 — Risk engine**
Each asset class shock is computed using actual risk math:
- Bonds: modified duration × rate shift
- Credit: spread duration × spread widening
- Loans: SOFR-linked floating benefit offsets spread hit
- Equities: beta × equity move + P/E compression from rates
- EM debt: rate + EM spread + implicit FX drag from USD strengthening

If you upload a Bloomberg PORT export, the engine uses your actual
durations and betas instead of defaults.

**Step 3 — Portfolio aggregation**
Contribution = weight × shock per asset class. Summed to portfolio
total return, VaR (95%), max drawdown estimate, and stress Sharpe.

**Step 4 — AI narrative**
The full context — scenario parameters, portfolio weights, asset shocks,
live market levels — is sent to Groq llama-3.3-70b. It returns a
practitioner-level commentary: primary transmission mechanism, most
exposed positions with reasoning, second-order risks (liquidity,
correlation breakdown, forced selling), and one specific hedge
instrument. Not generic — conditioned on your exact inputs.

---

## Features

- **6 scenarios** — Rate hike, Oil shock, Recession, Credit crunch,
  EM crisis, Custom. Every parameter has an adjustable slider.
- **Live data** — 30+ FRED series + 35+ yfinance tickers refreshed on
  every run.
- **Bloomberg PORT parser** — upload your `.xlsx` export, the tool reads
  real modified durations, spread durations, and betas automatically.
- **Correlation matrix** — normal conditions vs stressed regime
  (worst 10% equity days) side by side. See diversification break down.
- **AI narrative** — scenario commentary from Groq, free tier,
  no API cost.
- **Hedge suggestions** — separate AI call, returns 3 specific
  instruments with sizing logic.
- **Historical analog matching** — finds the 2 closest historical
  episodes (2008, 2020, 2022 etc.) using Euclidean distance on
  shock parameters.

---

## Quickstart

**1. Clone and set up**
```bash
git clone https://github.com/harshitkhandelwal/finance-ai-stack-04-stress-tester
cd finance-ai-stack-04-stress-tester
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Add API keys**

Create a `.env` file in the root:
```
FRED_API_KEY=your_fred_key
GROQ_API_KEY=your_groq_key
```

- FRED key: free at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
- Groq key: free at [console.groq.com](https://console.groq.com)

**3. Run**
```bash
streamlit run dashboard.py
```

Opens at `localhost:8501`.

---

## File structure
```
├── data_loader.py        # FRED + yfinance — pulls all live market data
├── bloomberg_parser.py   # Parses Bloomberg PORT .xlsx export
├── risk_engine.py        # Shock math, P&L aggregation, correlation, analog matching
├── scenario_builder.py   # 6 scenario definitions with slider ranges
├── groq_narrator.py      # AI narrative + hedge suggestions via Groq
├── dashboard.py          # Streamlit UI — wires everything together
└── requirements.txt
```

---

## Portfolio input

**Option A — Manual weights**
Type allocation % per asset class directly in the dashboard.

**Option B — Bloomberg PORT export**
Bloomberg terminal → `PORT` → Actions → Export → Excel.
Upload the `.xlsx` — the parser reads position-level durations,
spread durations, ratings, and betas automatically and aggregates
to asset class level.

---

## Honest limitations

This is a first-generation parametric model, not a production risk system.

It does not capture:
- **Convexity** — duration is linear; at large rate moves the error grows
- **Correlation breakdown in P&L** — the correlation matrix is shown but
  not used in the actual shock calculation
- **Liquidity premium** — exit costs in a stress scenario are not modeled
- **Sector granularity** — energy HY and consumer HY are treated as one
  bucket despite behaving very differently in an oil shock
- **Actual defaults** — spread widening is modeled but principal losses
  from defaults are not

The goal is the framework and the AI explanation layer — a base to
learn from and build on.

**V2 roadmap:**
- Regression-calibrated shock coefficients from historical data
- Correlation-adjusted portfolio P&L
- Sector-level granularity within HY and loans
- Convexity adjustment for long-duration bonds
- CLO tranche stress (AAA vs BB)
- PDF report export

---

## Tech stack

| Layer | Tool | Cost |
|---|---|---|
| Market data | FRED API + yfinance | Free |
| Risk math | NumPy + pandas | Free |
| AI narrative | Groq llama-3.3-70b | Free |
| Dashboard | Streamlit | Free |
| Charts | Plotly | Free |
| Bloomberg input | openpyxl parser | Free |

**Total cost: €0**

---

## Part of Finance × AI

This is Module 04 of an open-source series building real finance
tools with AI — one module at a time.


---

## About

Harshit Khandelwal — Leveraged Loans Analyst @ BNP Paribas Asset
Management, ESSEC MiM 2026, former Data Scientist @ Optum/UnitedHealth.

Building at the intersection of finance and AI.

https://www.linkedin.com/in/harshit-khandelwal-6278a4193/
https://github.com/khandelwalharshit1307/finance-ai-stack-03-portfolio-stress-tester
