import pandas as pd
import numpy as np
from pathlib import Path

INPUT = Path("data/raw/tracking_db.csv")
OUTPUT = Path("data/raw/tracking_db_demo.csv")

# Tunable knobs
N_IMOS = 80             # number of distinct vessels to keep
MAX_ROWS_PER_IMO = 600  # cap per vessel
MIN_ROWS_PER_IMO = 50   # ensure some sequence per vessel

# Common datetime columns seen in SmartPort datasets
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

def _to_epoch_seconds(parsed: pd.Series) -> pd.Series:
    """
    Convert a datetime64[ns] Series to epoch seconds (float).
    NaT becomes NaN.
    """
    # Ensure datetime dtype
    parsed = pd.to_datetime(parsed, errors="coerce", dayfirst=True)

    # pandas datetime64[ns] -> int64 nanoseconds since epoch
    # NaT becomes the minimum int64, so we mask it before converting
    ns = parsed.astype("int64")

    # Mask NaT (where parsed is NaT)
    ns = ns.where(parsed.notna(), np.nan)

    # Convert ns -> seconds
    return (ns / 1e9).astype("float64")


def _convert_datetime_cols_to_epoch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert datetime-like columns (strings) to epoch seconds (float).
    This prevents sklearn numeric imputers (e.g., median) from crashing at inference time.
    """
    df = df.copy()

    # 1) Convert known datetime candidate columns if present
    for col in DATETIME_CANDIDATES:
        if col in df.columns:
            df[col] = _to_epoch_seconds(df[col])

    # 2) Heuristic: if any remaining object column looks mostly like datetime, convert it too
    obj_cols = df.select_dtypes(include=["object"]).columns.tolist()
    for col in obj_cols:
        parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        if parsed.notna().mean() > 0.7:
            df[col] = _to_epoch_seconds(df[col])

    return df

def _coerce_object_cols_numeric_when_possible(df: pd.DataFrame) -> pd.DataFrame:
    """
    Try to convert remaining object columns to numeric.
    Non-convertible values become NaN.
    This makes the demo dataset more robust for numeric-only pipelines.
    """
    df = df.copy()
    obj_cols = df.select_dtypes(include=["object"]).columns.tolist()
    for col in obj_cols:
        # Attempt numeric coercion (if the column is categorical text, it will become mostly NaN)
        coerced = pd.to_numeric(df[col], errors="coerce")
        # Only replace if conversion yields at least some numeric signal
        # (prevents nuking purely categorical columns unnecessarily)
        if coerced.notna().mean() > 0.3:
            df[col] = coerced

    # Clean infinities
    df = df.replace([np.inf, -np.inf], np.nan)
    return df

def main():
    df = pd.read_csv(INPUT, low_memory=False)

    if "imo" not in df.columns:
        raise ValueError("Expected column 'imo' not found in tracking_db.csv")

    # Pick a set of IMOs with enough rows (keeps meaningful sequences)
    counts = df["imo"].value_counts(dropna=True)
    eligible_imos = counts[counts >= MIN_ROWS_PER_IMO].index.tolist()

    if len(eligible_imos) == 0:
        eligible_imos = df["imo"].dropna().unique().tolist()

    chosen_imos = eligible_imos[:N_IMOS]

    demo_parts = []
    for imo in chosen_imos:
        part = df[df["imo"] == imo].head(MAX_ROWS_PER_IMO)
        demo_parts.append(part)

    demo = pd.concat(demo_parts, ignore_index=True)

    # --- IMPORTANT: make the demo file model-friendly ---
    demo = _convert_datetime_cols_to_epoch(demo)
    demo = _coerce_object_cols_numeric_when_possible(demo)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    demo.to_csv(OUTPUT, index=False)

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"✅ Saved demo file: {OUTPUT} | rows={len(demo)} | size={size_mb:.2f} MB")

if __name__ == "__main__":
    main()