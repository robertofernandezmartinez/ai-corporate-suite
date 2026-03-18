import pandas as pd
import numpy as np
import joblib
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from sklearn.base import BaseEstimator, TransformerMixin
import __main__

logger = logging.getLogger(__name__)

# ============================================================
# FEATURE ENGINEERING: Keeping the numeric-only telemetry logic
# ============================================================
class NASAFeatureEngineer(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None): return self
    def transform(self, X):
        # Respecting your numeric casting for sensors
        return X.apply(pd.to_numeric, errors="coerce").fillna(0).values.astype(np.float64)

__main__.NASAFeatureEngineer = NASAFeatureEngineer

class NASAPredictor:
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except Exception: self.supabase = None
        
        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "nasa_model.pkl"
        self.pipeline = None
        self._load_engine()

    def _load_engine(self):
        if self.model_path.exists():
            self.pipeline = joblib.load(self.model_path)
            logger.info("✅ NASA Engine: ONLINE")

    async def predict_from_file(self, file):
        if not self.pipeline: return {"success": False, "detail": "Engine offline"}
        try:
            # Handles NASA's txt/csv space-separated format
            df_raw = pd.read_csv(file.file, sep=None, engine='python')
            
            # Security Shield: Sensor count check
            if df_raw.shape[1] < 20:
                return {"success": False, "detail": "NASA Telemetry incomplete. Check sensors."}

            predicted_rul = self.pipeline.predict(df_raw).astype(float)
            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_raw))],
                "batch_id": batch_id,
                "unit_id": df_raw.iloc[:, 0].astype(int), 
                "predicted_rul": predicted_rul,
                "timestamp": now_ts,
            })

            # Critical threshold for Push Notifications
            critical_engines = int((results_df["predicted_rul"] < 30).sum())

            if self.supabase: self._persist_batches(results_df, "nasa_predictions")

            return {
                "success": True,
                "processed_records": len(results_df),
                "summary": {"critical_engines": critical_engines},
                "batch_id": batch_id
            }
        except Exception as e: return {"success": False, "detail": str(e)}

    def _persist_batches(self, df, table_name):
        records = df.to_dict(orient="records")
        try:
            for i in range(0, len(records), 4000):
                self.supabase.table(table_name).insert(records[i:i+4000]).execute()
        except Exception as e: logger.warning(f"DB Error: {e}")