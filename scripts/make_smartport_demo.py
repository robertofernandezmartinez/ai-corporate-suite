import pandas as pd
from pathlib import Path

INPUT = Path("data/raw/tracking_db.csv")
OUTPUT = Path("data/raw/tracking_db_demo.csv")

# Tunable knobs
N_IMOS = 80          # number of distinct vessels to keep
MAX_ROWS_PER_IMO = 600  # cap per vessel

def main():
    df = pd.read_csv(INPUT, low_memory=False)

    if "imo" not in df.columns:
        raise ValueError("Expected column 'imo' not found in tracking_db.csv")

    # Pick a set of IMOs with enough rows (keeps meaningful sequences)
    counts = df["imo"].value_counts()
    eligible_imos = counts[counts >= 50].index.tolist()  # ensure some sequence per vessel

    if len(eligible_imos) == 0:
        eligible_imos = df["imo"].dropna().unique().tolist()

    chosen_imos = eligible_imos[:N_IMOS]

    demo_parts = []
    for imo in chosen_imos:
        part = df[df["imo"] == imo].head(MAX_ROWS_PER_IMO)
        demo_parts.append(part)

    demo = pd.concat(demo_parts, ignore_index=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    demo.to_csv(OUTPUT, index=False)

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"✅ Saved demo file: {OUTPUT} | rows={len(demo)} | size={size_mb:.2f} MB")

if __name__ == "__main__":
    main()