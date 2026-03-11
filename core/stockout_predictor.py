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


# ============================================================
# Feature Engineering Class (Mandatory for Joblib Loading)
# ============================================================
class StockoutFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Must exist for joblib unpickling.
    The actual transform logic is embedded inside the pickled pipeline.
    """
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X


__main__.StockoutFeatureEngineer = StockoutFeatureEngineer


# ============================================================
# Expected schema
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
# Helpers
# ============================================================
def _canonicalize_column_name(col: str) -> str:
    """
    Normalize raw column names to a comparison-safe format.
    Example:
        'Store ID' -> 'store_id'
        'Holiday/Promotion' -> 'holiday_promotion'
        ' Weather Condition ' -> 'weather_condition'
    """
    col = str(col).strip().lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)
    col = re.sub(r"_+", "_", col).strip("_")
    return col


def _build_column_mapping(df: pd.DataFrame) -> dict:
    """
    Build a robust mapping from incoming CSV columns to model schema.
    Supports both human-readable CSV headers and already-normalized names.
    """
    aliases = {
        "date": ["date", "Date"],
        "store_id": ["store_id", "Store ID", "store id"],
        "product_id": ["product_id", "Product ID", "product id"],
        "category": ["category", "Category"],
        "region": ["region", "Region"],
        "inventory_level": ["inventory_level", "Inventory Level", "inventory level"],
        "units_sold": ["units_sold", "Units Sold", "units sold"],
        "price": ["price", "Price"],
        "discount": ["discount", "Discount"],
        "weather": ["weather", "Weather Condition", "weather condition"],
        "holiday_promo": [
            "holiday_promo",
            "Holiday/Promotion",
            "holiday/promotion",
            "holiday promotion",
            "promo",
        ],
        "competitor_pricing": [
            "competitor_pricing",
            "Competitor Pricing",
            "competitor pricing",
        ],
        "seasonality": ["seasonality", "Seasonality"],
    }

    existing = {col: _canonicalize_column_name(col) for col in df.columns}
    reverse_existing = {canon: raw for raw, canon in existing.items()}

    rename_map = {}

    for target, candidates in aliases.items():
        for candidate in candidates:
            canon_candidate = _canonicalize_column_name(candidate)
            if canon_candidate in reverse_existing:
                rename_map[reverse_existing[canon_candidate]] = target
                break

    return rename_map


def _parse_date_column(series: pd.Series) -> pd.Series:
    """
    Parse dates robustly.
    Tries default parsing first, then day-first as fallback.
    """
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.notna().sum() == 0:
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return parsed


def _normalize_stockout_input(df: pd.DataFrame):
    """
    Normalize the uploaded Stockout CSV into the schema expected by the trained model.
    Returns:
        model_df: exact feature frame expected by the pipeline
        df_norm: normalized full dataframe for downstream use
    """
    df = df.copy()

    logger.info("📦 Stockout Normalize: raw columns = %s", list(df.columns))

    rename_map = _build_column_mapping(df)
    df = df.rename(columns=rename_map)

    logger.info("🔁 Stockout Normalize: rename map = %s", rename_map)
    logger.info("✅ Stockout Normalize: normalized columns = %s", list(df.columns))

    # Create derived date features
    if "date" in df.columns:
        parsed = _parse_date_column(df["date"])
        df["day_of_week"] = parsed.dt.dayofweek
        df["month"] = parsed.dt.month
        df["is_weekend"] = parsed.dt.dayofweek.isin([5, 6]).astype("float")
        logger.info(
            "📅 Stockout Features: date parsed successfully for %s/%s rows",
            int(parsed.notna().sum()),
            int(len(parsed)),
        )
    else:
        logger.warning("⚠️ Stockout Features: no date column found; derived features set to NaN")
        df["day_of_week"] = np.nan
        df["month"] = np.nan
        df["is_weekend"] = np.nan

    missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
    if missing:
        logger.error("❌ Stockout Normalize: missing required features after normalization: %s", missing)
        raise ValueError(f"columns are missing after normalization: {set(missing)}")

    model_df = df[REQUIRED_FEATURES].copy()

    for col in NUMERIC_COLS:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

    logger.info("🧪 Stockout Normalize: final model columns = %s", list(model_df.columns))
    logger.info("🧪 Stockout Normalize: model shape = %s", model_df.shape)

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
                logger.info("✅ Stockout Engine: Pipeline loaded from %s", self.model_path)
            else:
                logger.warning("⚠️ Stockout Engine: Model not found at %s", self.model_path)
        except Exception as e:
            logger.error("❌ Stockout Engine: Load Error: %s", e)
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
            logger.info("📥 Processing Stockout: %s", getattr(file, "filename", "uploaded_file.csv"))

            df_raw = pd.read_csv(file.file, low_memory=False)
            logger.info("📄 Stockout Input: shape=%s columns=%s", df_raw.shape, list(df_raw.columns))

            df_model, df_norm = _normalize_stockout_input(df_raw)

            logger.info("🚀 Stockout Inference: running predict_proba on shape=%s", df_model.shape)
            probabilities = self.pipeline.predict_proba(df_model)[:, 1].astype(float)

            price = pd.to_numeric(df_norm.get("price", 0), errors="coerce").fillna(0).astype(float)
            velocity = pd.to_numeric(df_norm.get("units_sold", 0), errors="coerce").fillna(0).astype(float)
            financial_impact = (probabilities * price * velocity).astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            product_id = df_norm.get(
                "product_id",
                pd.Series(["Unknown"] * len(df_norm), index=df_norm.index)
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
                self._persist_batches(results_df, table_name="stockout_predictions")

            logger.info(
                "✅ Stockout Success: processed=%s batch_id=%s total_exposure=%.2f",
                len(df_norm),
                batch_id,
                float(np.nan_to_num(results_df["financial_impact"]).sum()),
            )

            return {
                "success": True,
                "processed_records": int(len(df_norm)),
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
                self.supabase.table(table_name).insert(records[i:i + batch_size]).execute()
            logger.info("✅ Stockout Persistence: inserted %s rows into %s", len(records), table_name)
        except Exception as e:
            logger.warning("⚠️ Stockout Persistence Warning: %s", e)