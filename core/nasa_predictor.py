import pandas as pd
import numpy as np
import joblib
import uuid
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone
from sklearn.base import BaseEstimator, TransformerMixin
import __main__

logger = logging.getLogger(__name__)


# ============================================================
# Feature Engineering Class (Mandatory for Joblib Loading)
# ============================================================
class StockoutFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Must exist for joblib unpickling.
    The full transform logic lives inside the pickled pipeline.
    """
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X


__main__.StockoutFeatureEngineer = StockoutFeatureEngineer


# ============================================================
# Helpers
# ============================================================
REQUIRED_FEATURES = [
    "product_id",
    "holiday_promo",
    "competitor_pricing",
    "price",
    "store_id",
    "day_of_week",
    "discount",
    "inventory_level",
    "units_sold",
    "category",
    "month",
    "seasonality",
    "weather",
    "region",
    "is_weekend",
]


def _normalize_stockout_input(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the uploaded Stockout CSV into the schema expected by the trained model.

    Supported input:
    - PRO retail dataset with human-readable columns:
      Date, Store ID, Product ID, Category, Region, Inventory Level, Units Sold,
      Price, Discount, Weather Condition, Holiday/Promotion, Competitor Pricing, Seasonality

    Output:
    - snake_case columns expected by the model
    - engineered time features: day_of_week, month, is_weekend
    """
    df = df.copy()

    rename_map = {
        "Date": "date",
        "Store ID": "store_id",
        "Product ID": "product_id",
        "Category": "category",
        "Region": "region",
        "Inventory Level": "inventory_level",
        "Units Sold": "units_sold",
        "Price": "price",
        "Discount": "discount",
        "Weather Condition": "weather",
        "Holiday/Promotion": "holiday_promo",
        "Competitor Pricing": "competitor_pricing",
        "Seasonality": "seasonality",
    }

    df = df.rename(columns=rename_map)

    # Build engineered time features from date
    if "date" in df.columns:
        parsed = pd.to_datetime(df["date"], errors="coerce")
        df["day_of_week"] = parsed.dt.dayofweek
        df["month"] = parsed.dt.month
        df["is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype(int)
    else:
        df["day_of_week"] = np.nan
        df["month"] = np.nan
        df["is_weekend"] = np.nan

    # Ensure required columns exist
    missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"columns are missing: {set(missing)}")

    # Keep only model features for prediction
    model_df = df[REQUIRED_FEATURES].copy()

    # Numeric coercion for numeric fields
    numeric_cols = [
        "competitor_pricing",
        "price",
        "day_of_week",
        "discount",
        "inventory_level",
        "units_sold",
        "month",
        "is_weekend",
    ]

    for col in numeric_cols:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

    # Keep output ids from normalized dataframe
    return model_df, df


# ============================================================
# Predictor
# ============================================================
class StockoutPredictor:
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except Exception:
            self.supabase = None

        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "stockout_model.pkl"

        self.pipeline = None
        self._load_engine()

    def _load_engine(self):
        try:
            if self.model_path.exists():
                self.pipeline = joblib.load(self.model_path)
                logger.info("✅ Stockout Engine: Pipeline loaded.")
            else:
                logger.warning(f"⚠️ Stockout Engine: Model not found at {self.model_path}")
        except Exception as e:
            logger.error(f"❌ Stockout Engine: Load Error: {e}")
            self.pipeline = None

    def _risk_level(self, p: float) -> str:
        if p >= 0.80:
            return "CRITICAL"
        if p >= 0.50:
            return "HIGH"
        if p >= 0.20:
            return "MEDIUM"
        return "LOW"

    async def predict_from_file(self, file):
        if not self.pipeline:
            return {"success": False, "detail": "Stockout engine not initialized"}

        try:
            df_raw = pd.read_csv(file.file, low_memory=False)

            # Normalize uploaded raw CSV into model-ready schema
            df_model, df_norm = _normalize_stockout_input(df_raw)

            probabilities = self.pipeline.predict_proba(df_model)[:, 1].astype(float)

            # Lightweight impact proxy
            price = pd.to_numeric(df_norm.get("price", 0), errors="coerce").fillna(0).astype(float)
            velocity = pd.to_numeric(df_norm.get("units_sold", 0), errors="coerce").fillna(0).astype(float)
            financial_impact = (probabilities * price * velocity).astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            product_id = df_norm.get("product_id", pd.Series(["Unknown"] * len(df_norm))).astype(str)

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_norm))],
                "batch_id": batch_id,
                "created_at": now_ts,
                "product_id": product_id,
                "risk_score": probabilities,
                "risk_level": [self._risk_level(p) for p in probabilities],
                "financial_impact": financial_impact,
                "timestamp": now_ts,
            })

            if self.supabase:
                self._persist_batches(results_df, table_name="stockout_predictions")

            return {
                "success": True,
                "processed_records": int(len(df_norm)),
                "total_exposure": float(np.nan_to_num(results_df["financial_impact"]).sum()),
                "distribution": results_df["risk_level"].value_counts().to_dict(),
                "batch_id": batch_id
            }

        except Exception as e:
            logger.error(f"❌ Stockout Runtime Error:\n{traceback.format_exc()}")
            return {"success": False, "detail": str(e)}

    def _persist_batches(self, df: pd.DataFrame, table_name: str, batch_size: int = 4000):
        records = df.to_dict(orient="records")
        try:
            for i in range(0, len(records), batch_size):
                self.supabase.table(table_name).insert(records[i:i + batch_size]).execute()
            logger.info(f"✅ Stockout Persistence: inserted {len(records)} rows into {table_name}")
        except Exception as e:
            logger.warning(f"⚠️ Stockout Persistence Warning: {e}")