import os
import asyncio
from pathlib import Path

from core.nasa_predictor import NASAPredictor
from core.smartport_predictor import SmartPortPredictor
from core.stockout_predictor import StockoutPredictor


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data" / "raw"


class FakeUpload:
    """
    Simulates FastAPI UploadFile object for predictors.
    """
    def __init__(self, filepath: Path):
        self.file = open(filepath, "rb")


async def run_reload():

    print("🚀 Starting automated demo reload...")

    # === NASA === 
    nasa_file = DATA_DIR / "train_FD001.txt"
    if nasa_file.exists():
        print("Loading NASA demo dataset...")
        predictor = NASAPredictor()
        result = await predictor.predict_from_file(FakeUpload(nasa_file))
        print("NASA:", result)
    else:
        print("NASA file not found:", nasa_file)

    # === SMARTPORT ===
    smartport_file = DATA_DIR / "tracking_db.csv"
    if smartport_file.exists():
        print("Loading SmartPort demo dataset...")
        predictor = SmartPortPredictor()
        result = await predictor.predict_from_file(FakeUpload(smartport_file))
        print("SmartPort:", result)
    else:
        print("SmartPort file not found:", smartport_file)

    # === STOCKOUT ===
    stockout_file = DATA_DIR / "retail_store_inventory_PRO.csv"
    if stockout_file.exists():
        print("Loading Stockout demo dataset...")
        predictor = StockoutPredictor()
        result = await predictor.predict_from_file(FakeUpload(stockout_file))
        print("Stockout:", result)
    else:
        print("Stockout file not found:", stockout_file)

    print("✅ Demo reload completed.")


if __name__ == "__main__":
    asyncio.run(run_reload())