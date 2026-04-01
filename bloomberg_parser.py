# bloomberg_parser.py
import pandas as pd

# Bloomberg PORT export columns we care about
BBG_COL_MAP = {
    "Security Description":  "name",
    "Asset Class":           "asset_class",
    "Weight (%)":            "weight_pct",
    "Market Value":          "market_value",
    "Modified Duration":     "mod_duration",
    "DV01":                  "dv01",
    "Spread Duration":       "spread_duration",
    "OAS (bps)":             "oas_bps",
    "Rating":                "rating",
    "Currency":              "currency",
    "Country":               "country",
    "Coupon (%)":            "coupon",
    "Maturity":              "maturity",
    "Beta":                  "beta",
    "Yield to Worst (%)":    "ytw",
}

ASSET_CLASS_NORMALIZER = {
    "Government":            "Gov bonds",
    "Government Bond":       "Gov bonds",
    "Corp IG":               "IG credit",
    "Investment Grade":      "IG credit",
    "Corp HY":               "HY credit",
    "High Yield":            "HY credit",
    "Leveraged Loan":        "Leveraged loans",
    "Bank Loan":             "Leveraged loans",
    "Equity":                "Equities",
    "Equities":              "Equities",
    "EM Debt":               "EM debt",
    "Emerging Market":       "EM debt",
    "Commodity":             "Commodities",
    "Cash":                  "Cash",
    "Money Market":          "Cash",
}


def parse_bloomberg_export(filepath: str) -> pd.DataFrame:
    """
    Parse a Bloomberg PORT .xlsx export.
    Returns a clean DataFrame with standardized columns.
    """
    # Try both common tab names Bloomberg uses
    for sheet in ["Positions", "PORT - Positions", "Sheet1"]:
        try:
            raw = pd.read_excel(filepath, sheet_name=sheet, header=0)
            break
        except Exception:
            continue
    else:
        # Fallback: read first sheet
        raw = pd.read_excel(filepath, sheet_name=0, header=0)

    # Strip whitespace from column names
    raw.columns = raw.columns.str.strip()

    # Keep only columns we have in the map
    available = {k: v for k, v in BBG_COL_MAP.items() if k in raw.columns}
    df = raw[list(available.keys())].copy()
    df.rename(columns=available, inplace=True)

    # Drop rows with no name or zero weight
    df = df.dropna(subset=["name"])
    if "weight_pct" in df.columns:
        df = df[df["weight_pct"].apply(
            lambda x: pd.to_numeric(x, errors="coerce")
        ).fillna(0) > 0]
        df["weight_pct"] = pd.to_numeric(df["weight_pct"], errors="coerce").fillna(0)

    # Normalize asset class labels
    if "asset_class" in df.columns:
        df["asset_class"] = df["asset_class"].map(
            lambda x: ASSET_CLASS_NORMALIZER.get(str(x).strip(), str(x).strip())
        )

    # Numeric coercion
    for col in ["mod_duration", "dv01", "spread_duration", "oas_bps",
                "coupon", "beta", "ytw", "market_value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)


def aggregate_by_asset_class(df: pd.DataFrame) -> pd.DataFrame:
    """
    Roll up position-level data to asset-class level.
    Returns weight, weighted avg duration, spread duration, beta per class.
    """
    def wavg(group, val_col, wt_col="weight_pct"):
        v = pd.to_numeric(group[val_col], errors="coerce")
        w = pd.to_numeric(group[wt_col], errors="coerce")
        mask = v.notna() & w.notna() & (w > 0)
        if mask.sum() == 0:
            return None
        return round((v[mask] * w[mask]).sum() / w[mask].sum(), 4)

    rows = []
    for ac, grp in df.groupby("asset_class"):
        row = {
            "asset_class":      ac,
            "weight_pct":       round(grp["weight_pct"].sum(), 2),
            "mod_duration":     wavg(grp, "mod_duration") if "mod_duration" in grp.columns else None,
            "spread_duration":  wavg(grp, "spread_duration") if "spread_duration" in grp.columns else None,
            "beta":             wavg(grp, "beta") if "beta" in grp.columns else None,
            "oas_bps":          wavg(grp, "oas_bps") if "oas_bps" in grp.columns else None,
            "n_positions":      len(grp),
        }
        rows.append(row)

    return pd.DataFrame(rows).sort_values("weight_pct", ascending=False).reset_index(drop=True)