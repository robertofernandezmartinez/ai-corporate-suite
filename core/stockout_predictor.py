import pandas as pd
import numpy as np
import joblib
import uuid
import logging
import traceback
import re
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

CATEGORICAL_COLS = [
    "product_id",
    "holiday_promo",
    "store_id",
    "category",
    "seasonality",
    "weather",
    "region",
]


def _canonicalize(col: str) -> str:
    col = str(col).strip().lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)
    col = re.sub(r"_+", "_", col).strip("_")
    return col


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_canonicalize(c) for c in df.columns]
    return df


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    alias_map = {
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
        "weather": "weather",
        "holiday_promotion": "holiday_promo",
        "holiday_promo": "holiday_promo",
        "competitor_pricing": "competitor_pricing",
        "seasonality": "seasonality",
    }
    return df.rename(columns=alias_map)


def _safe_to_datetime(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.notna().sum() == 0:
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return parsed


def _clean_numeric(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")

    s = series.copy()

    s = s.astype(str)
    s = s.str.strip()
    s = s.str.replace("%", "", regex=False)
    s = s.str.replace(",", "", regex=False)

    replacements = {
        "": np.nan,
        "nan": np.nan,
        "none": np.nan,
        "null": np.nan,
        "na": np.nan,
        "n/a": np.nan,
        "missing": np.nan,
    }
    s = s.str.lower().replace(replacements)

    s = pd.to_numeric(s, errors="coerce")
    s = s.astype("float64")

    return s


def _clean_categorical(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype="object")

    s = series.copy()
    s = s.replace({pd.NA: np.nan})
    s = s.astype("object")
    s = s.where(pd.notna(s), "Unknown")
    s = s.astype(str).str.strip()
    s = s.replace({"": "Unknown", "nan": "Unknown", "None": "Unknown", "null": "Unknown"})
    return s


def _normalize_holiday_promo(series: pd.Series) -> pd.Series:
    s = _clean_categorical(series).str.lower()

    mapping = {
        "1": "1",
        "0": "0",
        "true": "1",
        "false": "0",
        "yes": "1",
        "no": "0",
        "y": "1",
        "n": "0",
        "holiday": "1",
        "no holiday": "0",
        "promo": "1",
        "promotion": "1",
        "holiday/promotion": "1",
        "none": "0",
        "unknown": "Unknown",
    }

    return s.map(lambda x: mapping.get(x, x)).astype(str)


def _prepare_model_input(df_raw: pd.DataFrame):
    df = _normalize_headers(df_raw)
    df = _rename_columns(df)

    if "date" in df.columns:
        parsed = _safe_to_datetime(df["date"])
        df["day_of_week"] = parsed.dt.dayofweek.astype("float64")
        df["month"] = parsed.dt.month.astype("float64")
        df["is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype("float64")
    else:
        df["day_of_week"] = pd.Series(np.nan, index=df.index, dtype="float64")
        df["month"] = pd.Series(np.nan, index=df.index, dtype="float64")
        df["is_weekend"] = pd.Series(np.nan, index=df.index, dtype="float64")

    missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"columns are missing: {set(missing)}")

    model_df = df[REQUIRED_FEATURES].copy()

    for col in NUMERIC_COLS:
        model_df[col] = _clean_numeric(model_df[col])

    for col in CATEGORICAL_COLS:
        model_df[col] = _clean_categorical(model_df[col])

    model_df["holiday_promo"] = _normalize_holiday_promo(model_df["holiday_promo"])

    model_df = model_df.replace({pd.NA: np.nan})
    model_df = model_df.loc[:, REQUIRED_FEATURES]

    for col in NUMERIC_COLS:
        model_df[col] = model_df[col].astype("float64")

    for col in CATEGORICAL_COLS:
        model_df[col] = model_df[col].astype("object")

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
            df_model, df_norm = _prepare_model_input(df_raw)

            probabilities = self.pipeline.predict_proba(df_model)[:, 1].astype(float)

            price = _clean_numeric(df_norm["price"]) if "price" in df_norm.columns else pd.Series(0.0, index=df_norm.index)
            units_sold = _clean_numeric(df_norm["units_sold"]) if "units_sold" in df_norm.columns else pd.Series(0.0, index=df_norm.index)
            price = price.fillna(0.0).astype("float64")
            units_sold = units_sold.fillna(0.0).astype("float64")

            financial_impact = (probabilities * price * units_sold).astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            if "product_id" in df_norm.columns:
                product_id = _clean_categorical(df_norm["product_id"])
            else:
                product_id = pd.Series(["Unknown"] * len(df_norm), index=df_norm.index, dtype="object")

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_norm))],
                "batch_id": batch_id,
                "created_at": now_ts,
                "product_id": product_id.astype(str),
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