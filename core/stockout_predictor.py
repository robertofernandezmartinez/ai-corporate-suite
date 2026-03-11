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


class StockoutFeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.cat_cols = [
            "store_id",
            "category",
            "region",
            "weather",
            "holiday_promo",
            "seasonality",
            "month",
            "day_of_week",
            "product_id",
        ]
        self.num_cols = [
            "inventory_level",
            "units_sold",
            "price",
            "discount",
            "competitor_pricing",
            "is_weekend",
        ]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()

        mapping = {
            "Date": "date",
            "Store ID": "store_id",
            "Product ID": "product_id",
            "Category": "category",
            "Region": "region",
            "Inventory Level": "inventory_level",
            "Units Sold": "units_sold",
            "Units Ordered": "units_ordered",
            "Price": "price",
            "Discount": "discount",
            "Weather Condition": "weather",
            "Holiday/Promotion": "holiday_promo",
            "Competitor Pricing": "competitor_pricing",
            "Seasonality": "seasonality",
        }

        df = df.rename(columns=mapping)

        if "date" in df.columns:
            date_dt = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
            df["month"] = date_dt.dt.month.astype(str)
            df["day_of_week"] = date_dt.dt.dayofweek.astype(str)
            df["is_weekend"] = date_dt.dt.dayofweek.isin([5, 6]).astype(float)

        for col in self.cat_cols:
            if col not in df.columns:
                df[col] = "Unknown"
            df[col] = df[col].astype(str)

        for col in self.num_cols:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df[self.cat_cols + self.num_cols]


__main__.StockoutFeatureEngineer = StockoutFeatureEngineer


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

            probabilities = self.pipeline.predict_proba(df_raw)[:, 1].astype(float)

            price = pd.to_numeric(df_raw.get("Price", 0), errors="coerce").fillna(0.0).astype(float)
            units_sold = pd.to_numeric(df_raw.get("Units Sold", 0), errors="coerce").fillna(0.0).astype(float)
            financial_impact = (probabilities * price * units_sold).astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            product_id = df_raw.get(
                "Product ID",
                pd.Series(["Unknown"] * len(df_raw), index=df_raw.index)
            ).astype(str)

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_raw))],
                "batch_id": batch_id,
                "created_at": now_ts,
                "product_id": product_id,
                "risk_score": probabilities,
                "risk_level": [self._risk_level(p) for p in probabilities],
                "financial_impact": financial_impact,
                "timestamp": now_ts,
            })

            if self.supabase:
                self._persist_batches(results_df, "stockout_predictions")

            return {
                "success": True,
                "processed_records": int(len(results_df)),
                "total_exposure": float(np.nan_to_num(results_df["financial_impact"]).sum()),
                "distribution": results_df["risk_level"].value_counts().to_dict(),
                "batch_id": batch_id,
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