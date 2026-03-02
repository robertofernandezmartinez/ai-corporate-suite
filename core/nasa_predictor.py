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
class NASAFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    This class must exist for joblib to unpickle the trained pipeline.
    Keep the name identical to the one used during training.
    """

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()

        # Convert everything to numeric; unknown becomes NaN then filled to 0.
        df = df.apply(pd.to_numeric, errors="coerce").fillna(0)

        return df.values.astype(np.float64)


# Register class for joblib
__main__.NASAFeatureEngineer = NASAFeatureEngineer


# ============================================================
# Predictor
# ============================================================
class NASAPredictor:
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except Exception:
            self.supabase = None

        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "nasa_model.pkl"

        self.pipeline = None
        self._load_engine()

    def _load_engine(self):
        try:
            if self.model_path.exists():
                self.pipeline = joblib.load(self.model_path)
                logger.info("✅ NASA Engine: Pipeline loaded.")
            else:
                logger.warning(f"⚠️ NASA Engine: Model not found at {self.model_path}")
        except Exception as e:
            logger.error(f"❌ NASA Engine: Load Error: {e}")
            self.pipeline = None

    async def predict_from_file(self, file):
        if not self.pipeline:
            return {"success": False, "detail": "NASA engine not initialized"}

        try:
            df_raw = pd.read_csv(file.file, low_memory=False)

            # Required columns for correct degradation plotting
            for col in ["unit_id", "cycle"]:
                if col not in df_raw.columns:
                    return {"success": False, "detail": f"Missing required column: {col}"}

            # Build features: drop identifiers
            X = df_raw.drop(columns=["unit_id", "cycle"], errors="ignore")

            # Predict RUL
            predicted_rul = self.pipeline.predict(X).astype(float)

            # New batch id per upload
            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_raw))],
                "batch_id": batch_id,
                "created_at": now_ts,
                "unit_id": pd.to_numeric(df_raw["unit_id"], errors="coerce").fillna(0).astype(int),
                "cycle": pd.to_numeric(df_raw["cycle"], errors="coerce").fillna(0).astype(int),
                "predicted_rul": predicted_rul,
                "timestamp": now_ts,
            })

            if self.supabase:
                self._persist_batches(results_df, table_name="nasa_predictions")

            return {
                "success": True,
                "processed_records": int(len(results_df)),
                "batch_id": batch_id
            }

        except Exception as e:
            logger.error(f"❌ NASA Runtime Error:\n{traceback.format_exc()}")
            return {"success": False, "detail": str(e)}

    def _persist_batches(self, df: pd.DataFrame, table_name: str, batch_size: int = 4000):
        records = df.to_dict(orient="records")
        try:
            for i in range(0, len(records), batch_size):
                self.supabase.table(table_name).insert(records[i:i + batch_size]).execute()
            logger.info(f"✅ NASA Persistence: inserted {len(records)} rows into {table_name}")
        except Exception as e:
            logger.warning(f"⚠️ NASA Persistence Warning: {e}")