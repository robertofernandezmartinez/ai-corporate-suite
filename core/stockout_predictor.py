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
DATETIME_CANDIDATES = [
    "date",
    "Date",
    "order_date",
    "Order Date",
    "sales_date",
    "Sales Date",
    "timestamp",
    "Timestamp",
]


def _coerce_stockout_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make the Stockout raw dataframe safe for numeric sklearn imputers.

    Why:
    - The trained pipeline includes SimpleImputer(strategy='median'), which requires numeric input.
    - If date columns arrive as strings (e.g. '2022-01-01'), sklearn will crash.

    What we do:
    1) Convert known datetime-like columns to epoch seconds.
    2) For any remaining object columns, attempt datetime parsing first.
    3) If not datetime, attempt numeric coercion.
    4) Keep identifiers needed later for the output dataframe from the original raw input.
    """
    df = df.copy()

    # 1) Convert known datetime columns to epoch seconds
    for col in DATETIME_CANDIDATES:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            df[col] = (parsed.astype("int64") / 1e9).where(parsed.notna(), np.nan).astype("float64")

    # 2) Convert remaining object columns
    obj_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    for col in obj_cols:
        # First try datetime
        parsed_dt = pd.to_datetime(df[col], errors="coerce")
        if parsed_dt.notna().mean() > 0.7:
            df[col] = (parsed_dt.astype("int64") / 1e9).where(parsed_dt.notna(), np.nan).astype("float64")
            continue

        # Then try numeric
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clean infinities
    df = df.replace([np.inf, -np.inf], np.nan)

    return df


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

            # Keep original raw dataframe for output fields like product_id and impact inputs
            df_safe = _coerce_stockout_dataframe(df_raw)

            probabilities = self.pipeline.predict_proba(df_safe)[:, 1].astype(float)

            # Lightweight impact proxy (you can refine later)
            price = pd.to_numeric(
                df_raw.get("Price", df_raw.get("price", 0)),
                errors="coerce"
            ).fillna(0).astype(float)

            velocity = pd.to_numeric(
                df_raw.get("Units Sold", df_raw.get("units_sold", 0)),
                errors="coerce"
            ).fillna(0).astype(float)

            financial_impact = (probabilities * price * velocity).astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            product_id = df_raw.get(
                "Product ID",
                df_raw.get("product_id", "Unknown")
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
                self._persist_batches(results_df, table_name="stockout_predictions")

            return {
                "success": True,
                "processed_records": int(len(df_raw)),
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