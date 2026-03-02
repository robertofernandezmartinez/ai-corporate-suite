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
class SmartPortFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Must exist for joblib to unpickle the production pipeline.
    The real transformation logic is inside the pickled pipeline,
    but we keep a minimal compatible stub to avoid UnpicklingError.
    """
    def __init__(self):
        self.selected_features = [
            "day_of_week", "rolling_mean_sog", "hdg", "movement_stability",
            "cog", "speed_delta", "heading_change", "imo_te",
            "reporting_interval_min", "time_since_last_position_min", "arr_port_FIHEL"
        ]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        # The pickled pipeline contains the real logic.
        return X


__main__.SmartPortFeatureEngineer = SmartPortFeatureEngineer


# ============================================================
# Predictor
# ============================================================
class SmartPortPredictor:
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except Exception:
            self.supabase = None

        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "smartport_model.pkl"

        self.pipeline = None
        self._load_engine()

    def _load_engine(self):
        try:
            if self.model_path.exists():
                self.pipeline = joblib.load(self.model_path)
                logger.info("✅ SmartPort Engine: Pipeline loaded.")
            else:
                logger.warning(f"⚠️ SmartPort Engine: Model not found at {self.model_path}")
        except Exception as e:
            logger.error(f"❌ SmartPort Engine: Load Error: {e}")
            self.pipeline = None

    async def predict_from_file(self, file):
        if not self.pipeline:
            return {"success": False, "detail": "SmartPort engine not initialized"}

        try:
            df_raw = pd.read_csv(file.file, low_memory=False)

            probabilities = self.pipeline.predict_proba(df_raw)[:, 1].astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            def risk_level(p: float) -> str:
                if p >= 0.85:
                    return "CRITICAL"
                if p >= 0.50:
                    return "WARNING"
                return "NORMAL"

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_raw))],
                "batch_id": batch_id,
                "created_at": now_ts,
                "vessel_index": list(range(len(df_raw))),
                "risk_score": probabilities,
                "risk_level": [risk_level(p) for p in probabilities],
                "timestamp": now_ts,
            })

            if self.supabase:
                self._persist_batches(results_df, table_name="smartport_predictions")

            return {
                "success": True,
                "processed_records": int(len(df_raw)),
                "distribution": results_df["risk_level"].value_counts().to_dict(),
                "batch_id": batch_id
            }

        except Exception as e:
            logger.error(f"❌ SmartPort Runtime Error:\n{traceback.format_exc()}")
            return {"success": False, "detail": str(e)}

    def _persist_batches(self, df: pd.DataFrame, table_name: str, batch_size: int = 4000):
        records = df.to_dict(orient="records")
        try:
            for i in range(0, len(records), batch_size):
                self.supabase.table(table_name).insert(records[i:i + batch_size]).execute()
            logger.info(f"✅ SmartPort Persistence: inserted {len(records)} rows into {table_name}")
        except Exception as e:
            logger.warning(f"⚠️ SmartPort Persistence Warning: {e}")