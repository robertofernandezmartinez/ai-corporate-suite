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
# Feature Engineering Class (Required for Joblib)
# ============================================================

class StockoutFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Required so sklearn pipeline can unpickle the transformer.
    Actual transform logic lives inside the saved pipeline.
    """
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X


__main__.StockoutFeatureEngineer = StockoutFeatureEngineer


# ============================================================
# Expected Feature Schema
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


NUMERIC_COLS = [
    "competitor_pricing",
    "price",
    "day_of_week",
    "discount",
    "inventory_level",
    "units_sold",
    "month",
    "is_weekend",
]


# ============================================================
# Column Normalization
# ============================================================

def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize incoming CSV column names to stable format.
    """
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )
    return df


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map normalized CSV headers to model schema.
    """

    rename_map = {
        "date": "date",
        "store_id": "store_id",
        "product_id": "product_id",
        "category": "category",
        "region": "region",
        "inventory_level": "inventory_level",
        "units_sold": "units_sold",
        "price": "price",
        "discount": "discount",
        "weather_condition": "weather",
        "holiday_promotion": "holiday_promo",
        "competitor_pricing": "competitor_pricing",
        "seasonality": "seasonality",
    }

    df = df.rename(columns=rename_map)

    return df


# ============================================================
# Feature Engineering
# ============================================================

def _generate_time_features(df: pd.DataFrame) -> pd.DataFrame:

    if "date" not in df.columns:
        logger.warning("⚠️ No date column detected. Derived features will be NaN.")
        df["day_of_week"] = np.nan
        df["month"] = np.nan
        df["is_weekend"] = np.nan
        return df

    parsed = pd.to_datetime(df["date"], errors="coerce")

    df["day_of_week"] = parsed.dt.dayofweek
    df["month"] = parsed.dt.month
    df["is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype(float)

    logger.info(
        "📅 Date parsing: %s/%s valid rows",
        parsed.notna().sum(),
        len(parsed)
    )

    return df


# ============================================================
# Full Normalization Pipeline
# ============================================================

def _normalize_stockout_input(df: pd.DataFrame):

    df = df.copy()

    logger.info("📦 Raw input columns: %s", list(df.columns))

    df = _normalize_headers(df)
    df = _rename_columns(df)
    df = _generate_time_features(df)

    logger.info("🔁 Normalized columns: %s", list(df.columns))

    missing = [c for c in REQUIRED_FEATURES if c not in df.columns]

    if missing:
        raise ValueError(f"columns are missing: {set(missing)}")

    model_df = df[REQUIRED_FEATURES].copy()

    for col in NUMERIC_COLS:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

    logger.info("🧠 Model input shape: %s", model_df.shape)

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
                logger.warning("⚠️ Stockout model not found at %s", self.model_path)

        except Exception as e:
            logger.error("❌ Model load error: %s", e)
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

            logger.info("📥 Processing Stockout: %s", getattr(file, "filename", "uploaded.csv"))

            df_raw = pd.read_csv(file.file, low_memory=False)

            logger.info("📄 Input shape: %s", df_raw.shape)

            df_model, df_norm = _normalize_stockout_input(df_raw)

            logger.info("🚀 Running pipeline inference")

            probabilities = self.pipeline.predict_proba(df_model)[:, 1].astype(float)

            price = pd.to_numeric(df_norm.get("price", 0), errors="coerce").fillna(0)
            velocity = pd.to_numeric(df_norm.get("units_sold", 0), errors="coerce").fillna(0)

            financial_impact = (probabilities * price * velocity).astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            product_id = df_norm.get(
                "product_id",
                pd.Series(["Unknown"] * len(df_norm))
            ).astype(str)

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
                self._persist_batches(results_df, "stockout_predictions")

            logger.info(
                "✅ Stockout Success: %s rows processed",
                len(results_df)
            )

            return {

                "success": True,

                "processed_records": int(len(results_df)),

                "total_exposure": float(np.nan_to_num(results_df["financial_impact"]).sum()),

                "distribution": results_df["risk_level"].value_counts().to_dict(),

                "batch_id": batch_id,
            }

        except Exception as e:

            logger.error("❌ Stockout Runtime Error:\n%s", traceback.format_exc())

            return {"success": False, "detail": str(e)}


    def _persist_batches(self, df: pd.DataFrame, table_name: str, batch_size: int = 4000):

        records = df.to_dict(orient="records")

        try:

            for i in range(0, len(records), batch_size):

                self.supabase.table(table_name).insert(
                    records[i:i + batch_size]
                ).execute()

            logger.info(
                "✅ Stockout Persistence: inserted %s rows",
                len(records)
            )

        except Exception as e:

            logger.warning("⚠️ Supabase insert warning: %s", e)