import pandas as pd
import numpy as np
from pathlib import Path

INPUT = Path("data/raw/tracking_db.csv")
OUTPUT = Path("data/raw/tracking_db_demo.csv")

# Tunable knobs
N_IMOS = 80
MAX_ROWS_PER_IMO = 600
MIN_ROWS_PER_IMO = 50

DATETIME_CANDIDATES = {
    "timestamp",
    "updated_ts",
    "eta",
    "etd",
    "ata",
    "atd",
    "eta_schedule",
    "etd_schedule",
}

def _to_epoch_seconds(series: pd.Series) -> pd.Series:
    """Convert datetime-like series to epoch seconds (float). NaT -> NaN."""
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    ns = parsed.astype("int64")
    ns = ns.where(parsed.notna(), np.nan)
    return (ns / 1e9).astype("float64")

def _convert_known_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    """Convert known datetime columns to epoch seconds if they exist."""
    df = df.copy()
    for col in DATETIME_CANDIDATES:
        if col in df.columns:
            df[col] = _to_epoch_seconds(df[col])
    return df

def _drop_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop columns that contain non-numeric text (e.g. vessel names like 'Megastar').
    Keep only:
      - numeric columns
      - boolean columns
      - (optionally) 'imo' if present (often numeric anyway)
    """
    df = df.copy()

    # Coerce boolean to int (optional, but keeps everything numeric-friendly)
    bool_cols = df.select_dtypes(include=["bool"]).columns.tolist()
    for c in bool_cols:
        df[c] = df[c].astype("int8")

    # Attempt numeric coercion for object/string columns; if too many NaNs -> drop
    text_like = df.select_dtypes(include=["object", "string"]).columns.tolist()
    for col in text_like:
        coerced = pd.to_numeric(df[col], errors="coerce")
        # If a column is mostly non-numeric, it's truly text/categorical -> drop it
        if coerced.notna().mean() < 0.8:
            df.drop(columns=[col], inplace=True)
        else:
            df[col] = coerced

    # Finally keep only numeric columns
    df = df.select_dtypes(include=[np.number])

    # Clean infinities
    df = df.replace([np.inf, -np.inf], np.nan)

    return df

def main():
    df = pd.read_csv(INPUT, low_memory=False)

    if "imo" not in df.columns:
        raise ValueError("Expected column 'imo' not found in tracking_db.csv")

    counts = df["imo"].value_counts(dropna=True)
    eligible_imos = counts[counts >= MIN_ROWS_PER_IMO].index.tolist()
    if not eligible_imos:
        eligible_imos = df["imo"].dropna().unique().tolist()

    chosen_imos = eligible_imos[:N_IMOS]

    demo_parts = []
    for imo in chosen_imos:
        part = df[df["imo"] == imo].head(MAX_ROWS_PER_IMO)
        demo_parts.append(part)

    demo = pd.concat(demo_parts, ignore_index=True)

    # Make demo numeric-only friendly
    demo = _convert_known_datetimes(demo)
    demo = _drop_text_columns(demo)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    demo.to_csv(OUTPUT, index=False)

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"✅ Saved demo file: {OUTPUT} | rows={len(demo)} | cols={demo.shape[1]} | size={size_mb:.2f} MB")

if __name__ == "__main__":
    main()