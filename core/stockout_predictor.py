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
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X


__main__.StockoutFeatureEngineer = StockoutFeatureEngineer


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


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )
    return df


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:

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

    return df.rename(columns=rename_map)


def _generate_time_features(df: pd.DataFrame) -> pd.DataFrame:

    if "date" not in df.columns:
        df["day_of_week"] = np.nan
        df["month"] = np.nan
        df["is_weekend"] = np.nan
        return df

    parsed = pd.to_datetime(df["date"], errors="coerce")

    df["day_of_week"] = parsed.dt.dayofweek
    df["month"] = parsed.dt.month
    df["is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype(int)

    return df


def _clean_numeric(series):
    return (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace(["", "nan", "None"], np.nan)
        .astype(float)
    )


def _normalize_stockout_input(df: pd.DataFrame):

    df = df.copy()

    df = _normalize_headers(df)
    df = _rename_columns(df)
    df = _generate_time_features(df)

    missing = [c for c in REQUIRED_FEATURES if c not in df.columns]

    if missing:
        raise ValueError(f"columns are missing: {set(missing)}")

    model_df = df[REQUIRED_FEATURES].copy()

    for col in NUMERIC_COLS:
        model_df[col] = _clean_numeric(model_df[col])

    return model_df, df


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
                logger.info("Stockout Engine Loaded")

            else:
                logger.warning(f"Model not found at {self.model_path}")

        except Exception as e:

            logger.error(f"Model Load Error: {e}")
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

            df_model, df_norm = _normalize_stockout_input(df_raw)

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

            return {

                "success": True,

                "processed_records": int(len(results_df)),

                "total_exposure": float(np.nan_to_num(results_df["financial_impact"]).sum()),

                "distribution": results_df["risk_level"].value_counts().to_dict(),

                "batch_id": batch_id,
            }

        except Exception as e:

            logger.error(traceback.format_exc())

            return {"success": False, "detail": str(e)}


    def _persist_batches(self, df: pd.DataFrame, table_name: str, batch_size: int = 4000):

        records = df.to_dict(orient="records")

        try:

            for i in range(0, len(records), batch_size):

                self.supabase.table(table_name).insert(
                    records[i:i + batch_size]
                ).execute()

            logger.info(f"Inserted {len(records)} rows into {table_name}")

        except Exception as e:

            logger.warning(f"Supabase insert warning: {e}")