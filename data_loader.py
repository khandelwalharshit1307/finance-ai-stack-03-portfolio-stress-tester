# data_loader.py
# Finance x AI — Module 04: Portfolio Stress Tester
# Pulls live market data from FRED and yfinance
# Author: Harshit Khandelwal

import os
import pandas as pd
import yfinance as yf
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()
fred = Fred(api_key=os.getenv("FRED_API_KEY"))

# ─────────────────────────────────────────────
# FRED SERIES
# ─────────────────────────────────────────────
FRED_SERIES = {

    # Yield curve — US Treasuries
    "us_2y":            "DGS2",
    "us_5y":            "DGS5",
    "us_10y":           "DGS10",
    "us_30y":           "DGS30",

    # Short end / policy rate
    "fed_funds":        "FEDFUNDS",
    "sofr":             "SOFR",

    # Real rates / inflation expectations
    "tips_5y_be":       "T5YIE",        # 5Y breakeven inflation
    "tips_10y_be":      "T10YIE",       # 10Y breakeven inflation
    "tips_10y_real":    "DFII10",       # 10Y real yield

    # US credit spreads — ICE BofA indices
    "ig_oas":           "BAMLC0A0CM",   # US IG option-adjusted spread
    "hy_oas":           "BAMLH0A0HYM2", # US HY option-adjusted spread

    # IG by rating bucket
    "ig_aaa":           "BAMLC0A1CAAA",
    "ig_aa":            "BAMLC0A2CAA",
    "ig_a":             "BAMLC0A3CA",
    "ig_bbb":           "BAMLC0A4CBBB",

    # HY by rating bucket
    "hy_bb":            "BAMLH0A1HYBB",
    "hy_b":             "BAMLH0A2HYB",
    "hy_ccc":           "BAMLH0A3HYC",

    # European credit
    "eur_ig_oas":       "BAMLHE00EHY2Y",

    # Lending standards — proxy for loan market tightness
    "loan_standards":   "DRTSCILM",

    # Macro fundamentals
    "cpi_yoy":          "CPIAUCSL",
    "core_pce":         "PCEPILFE",
    "unemployment":     "UNRATE",
    "gdp_growth":       "A191RL1Q225SBEA",
    "lei":              "USSLIND",      # Conference Board LEI

    # FX — USD bilateral rates
    "eurusd":           "DEXUSEU",
    "usdjpy":           "DEXJPUS",
    "gbpusd":           "DEXUSUK",
    "usdcny":           "DEXCHUS",
    "usdmxn":           "DEXMXUS",

}

# ─────────────────────────────────────────────
# YFINANCE TICKERS
# ─────────────────────────────────────────────
YFINANCE_TICKERS = {

    # Broad equity indices
    "sp500":            "^GSPC",
    "nasdaq":           "^IXIC",
    "stoxx50":          "^STOXX50E",
    "ftse100":          "^FTSE",
    "nikkei":           "^N225",
    "em_equity":        "EEM",

    # Volatility
    "vix":              "^VIX",
    "move_proxy":       "TLT",          # MOVE not on yfinance; TLT vol used as proxy

    # US equity sectors
    "xlf":              "XLF",          # financials
    "xle":              "XLE",          # energy
    "xlk":              "XLK",          # technology
    "xlv":              "XLV",          # healthcare
    "xli":              "XLI",          # industrials
    "xlp":              "XLP",          # consumer staples
    "xly":              "XLY",          # consumer discretionary

    # Fixed income ETFs — used for beta / duration proxies
    "tlt":              "TLT",          # 20Y US Treasury
    "ief":              "IEF",          # 7-10Y US Treasury
    "shy":              "SHY",          # 1-3Y US Treasury
    "lqd":              "LQD",          # US IG corporate bonds
    "hyg":              "HYG",          # US HY corporate bonds
    "emb":              "EMB",          # EM sovereign USD bonds
    "bkln":             "BKLN",         # leveraged loans (Invesco)
    "jnk":              "JNK",          # HY bonds (SPDR)

    # Commodities
    "brent":            "BZ=F",         # Brent crude oil
    "wti":              "CL=F",         # WTI crude oil
    "natgas":           "NG=F",         # natural gas
    "gold":             "GC=F",         # gold
    "silver":           "SI=F",         # silver
    "copper":           "HG=F",         # copper — growth proxy
    "wheat":            "ZW=F",         # wheat
    "corn":             "ZC=F",         # corn

    # FX
    "dxy":              "DX-Y.NYB",     # US dollar index
    "em_fx":            "CEW",          # WisdomTree EM currency ETF
    "eurusd_fx":        "EURUSD=X",
    "usdjpy_fx":        "JPY=X",
    "gbpusd_fx":        "GBPUSD=X",

}

# ─────────────────────────────────────────────
# FETCH FUNCTIONS
# ─────────────────────────────────────────────

def fetch_fred_latest() -> dict:
    data = {}
    for name, code in FRED_SERIES.items():
        try:
            series = fred.get_series(code)
            series = series.dropna()

            # CPI: compute YoY % change instead of raw index level
            if name == "cpi_yoy":
                yoy = series.pct_change(12) * 100  # 12 months
                data[name] = round(float(yoy.dropna().iloc[-1]), 2)

            # Same for core PCE
            elif name == "core_pce":
                yoy = series.pct_change(12) * 100
                data[name] = round(float(yoy.dropna().iloc[-1]), 2)

            else:
                data[name] = round(float(series.iloc[-1]), 4)

        except Exception:
            data[name] = None
    return data


def fetch_yfinance_latest() -> dict:
    """
    Pull the latest close price for every yfinance ticker.
    Uses fast_info for speed — avoids full history download.
    """
    data = {}
    for name, ticker in YFINANCE_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info["lastPrice"]
            data[name] = round(float(price), 4)
        except Exception:
            data[name] = None
    return data


def fetch_returns_history(period: str = "2y") -> pd.DataFrame:
    """
    Pull daily closing prices for all yfinance tickers over the
    specified period, then compute daily % returns.

    Used for:
      - Beta computation (each position vs its benchmark)
      - Cross-asset correlation matrix
      - Volatility estimates

    fill_method=None suppresses the FutureWarning from pandas.
    """
    tickers = list(YFINANCE_TICKERS.values())

    raw = yf.download(
        tickers,
        period=period,
        auto_adjust=True,
        progress=False
    )["Close"]

    # Drop columns where we got no data at all
    raw = raw.dropna(axis=1, how="all")

    # Compute returns — fill_method=None avoids FutureWarning
    returns = raw.pct_change(fill_method=None).dropna()

    # Rename columns from ticker symbols back to our friendly names
    ticker_to_name = {v: k for k, v in YFINANCE_TICKERS.items()}
    returns.columns = [ticker_to_name.get(col, col) for col in returns.columns]

    return returns


def fetch_fred_history(series_list: list = None, period_years: int = 2) -> pd.DataFrame:
    """
    Pull historical time series for a subset of FRED series.
    Useful for plotting yield curves and spread history over time.

    Default series: yield curve + IG/HY spreads.
    """
    if series_list is None:
        series_list = ["us_2y", "us_5y", "us_10y", "us_30y", "ig_oas", "hy_oas"]

    cutoff = pd.Timestamp.today() - pd.DateOffset(years=period_years)
    frames = {}

    for name in series_list:
        code = FRED_SERIES.get(name)
        if not code:
            continue
        try:
            s = fred.get_series(code, observation_start=cutoff.strftime("%Y-%m-%d"))
            frames[name] = s.dropna()
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df


# ─────────────────────────────────────────────
# MASTER FUNCTION
# ─────────────────────────────────────────────

def get_all_market_data() -> dict:
    """
    Master loader — returns everything the risk engine needs.

    Returns:
        {
            "fred":    dict  — latest value per FRED series
            "yf":      dict  — latest price per yfinance ticker
            "returns": DataFrame — daily returns for correlation + beta
        }
    """
    print("Fetching FRED data...")
    fred_data = fetch_fred_latest()

    print("Fetching yfinance prices...")
    yf_data = fetch_yfinance_latest()

    print("Fetching return history (2Y)...")
    returns_df = fetch_returns_history(period="2y")

    print("Done.")
    return {
        "fred":    fred_data,
        "yf":      yf_data,
        "returns": returns_df,
    }


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    d = get_all_market_data()

    print("\n── FRED snapshot ──")
    keys_to_show = ["us_2y", "us_10y", "us_30y", "fed_funds",
                    "ig_oas", "hy_oas", "cpi_yoy", "unemployment"]
    for k in keys_to_show:
        print(f"  {k:20s}: {d['fred'].get(k)}")

    print("\n── yfinance snapshot ──")
    keys_to_show = ["sp500", "vix", "brent", "gold", "dxy",
                    "tlt", "hyg", "bkln"]
    for k in keys_to_show:
        print(f"  {k:20s}: {d['yf'].get(k)}")

    print(f"\n── Returns history ──")
    print(f"  Shape: {d['returns'].shape}")
    print(f"  Columns: {list(d['returns'].columns[:8])} ...")