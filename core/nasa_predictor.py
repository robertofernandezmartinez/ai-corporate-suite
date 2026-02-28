import pandas as pd
import numpy as np
import joblib
import uuid
import logging
import traceback
from pathlib import Path
from datetime import datetime
from sklearn.base import BaseEstimator, TransformerMixin
import __main__

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Feature Engineering (must match training pipeline)
# ---------------------------------------------------------------------

class NASAFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Custom transformer used during model training.
    It must be re-declared here so joblib can deserialize the pipeline.
    """

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()

        # Ensure numeric conversion
        numeric_cols = df.columns.tolist()
        df[numeric_cols] = df[numeric_cols].apply(
            pd.to_numeric, errors="coerce"
        )

        # Replace NaN with 0 (safe fallback)
        df = df.fillna(0)

        return df.values.astype(np.float64)


# Required for joblib to recognize custom transformer
__main__.NASAFeatureEngineer = NASAFeatureEngineer


# ---------------------------------------------------------------------
# NASA Predictor
# ---------------------------------------------------------------------

class NASAPredictor:
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except ImportError:
            self.supabase = None

        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "nasa_model.pkl"

        self.pipeline = None
        self._load_engine()

    # -----------------------------------------------------------------

    def _load_engine(self):
        """Load trained NASA RUL model pipeline."""
        try:
            if self.model_path.exists():
                self.pipeline = joblib.load(self.model_path)
                logger.info("✅ NASA Engine Model Loaded")
            else:
                logger.warning("⚠️ NASA model file not found.")
        except Exception as e:
            logger.error(f"❌ NASA Model Load Error: {e}")

    # -----------------------------------------------------------------

    async def predict_from_file(self, file):
        """
        Accepts uploaded CSV file,
        generates RUL predictions,
        stores results in Supabase.
        """

        if not self.pipeline:
            return {"success": False, "detail": "Model not initialized"}

        try:
            df_raw = pd.read_csv(file.file, low_memory=False)

            # Ensure required columns exist
            required_cols = ["unit_id", "cycle"]
            for col in required_cols:
                if col not in df_raw.columns:
                    return {
                        "success": False,
                        "detail": f"Missing required column: {col}"
                    }

            # Separate features from identifiers
            feature_df = df_raw.drop(columns=["unit_id", "cycle"], errors="ignore")

            predictions = self.pipeline.predict(feature_df)

            now_ts = datetime.utcnow().isoformat()

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_raw))],
                "unit_id": df_raw["unit_id"].values,
                "cycle": df_raw["cycle"].values.astype(int),
                "predicted_rul": predictions.astype(float),
                "timestamp": now_ts
            })

            if self.supabase:
                self._persist_batches(results_df)

            return {
                "success": True,
                "processed_records": len(results_df)
            }

        except Exception as e:
            logger.error(f"❌ NASA Runtime Error: {traceback.format_exc()}")
            return {"success": False, "detail": str(e)}

    # -----------------------------------------------------------------

    def _persist_batches(self, df: pd.DataFrame):
        """
        Insert predictions into Supabase in batches.
        """

        table_name = "nasa_predictions"
        batch_size = 4000
        records = df.to_dict(orient="records")

        try:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]

                self.supabase.table(table_name).upsert(
                    batch,
                    on_conflict="unit_id,cycle"
                ).execute()

            logger.info("✅ NASA Predictions Persisted Successfully")

        except Exception as e:
            logger.warning(f"⚠️ Supabase Insert Error: {e}")