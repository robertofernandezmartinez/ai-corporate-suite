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
# FEATURE ENGINEERING: Keeping the same structure to avoid UnpicklingError
# ============================================================
class SmartPortFeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self):
        # Same feature list as your tracking_db version
        self.selected_features = ["day_of_week", "rolling_mean_sog", "hdg", "movement_stability", "cog", "speed_delta", "heading_change", "imo_te"]
    def fit(self, X, y=None): return self
    def transform(self, X): return X

__main__.SmartPortFeatureEngineer = SmartPortFeatureEngineer

class SmartPortPredictor:
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except Exception: self.supabase = None
        
        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "smartport_model.pkl"
        self.pipeline = None
        self._load_engine()

    def _load_engine(self):
        if self.model_path.exists():
            self.pipeline = joblib.load(self.model_path)
            logger.info("✅ SmartPort Engine: ONLINE")

    async def predict_from_file(self, file):
        if not self.pipeline: return {"success": False, "detail": "Engine offline"}
        try:
            df_raw = pd.read_csv(file.file, low_memory=False)
            
            # Security Shield: AIS columns validation
            required = ["imo", "sog", "cog", "hdg"]
            missing = [c for c in required if c not in df_raw.columns]
            if missing:
                return {"success": False, "detail": f"SmartPort format invalid. Missing: {missing}"}

            probabilities = self.pipeline.predict_proba(df_raw)[:, 1].astype(float)
            max_prob = float(np.max(probabilities))
            
            risk = "NORMAL"
            if max_prob >= 0.85: risk = "CRITICAL"
            elif max_prob >= 0.50: risk = "WARNING"

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_raw))],
                "batch_id": batch_id, 
                "created_at": now_ts,
                "vessel_index": list(range(len(df_raw))),
                "risk_score": probabilities,
                "risk_level": ["CRITICAL" if p >= 0.85 else "WARNING" if p >= 0.5 else "NORMAL" for p in probabilities],
                "timestamp": now_ts,
            })

            if self.supabase: self._persist_batches(results_df, "smartport_predictions")

            return {
                "success": True,
                "processed_records": len(df_raw),
                "summary": {"risk_level": risk, "max_score": max_prob},
                "batch_id": batch_id
            }
        except Exception as e: return {"success": False, "detail": str(e)}

    def _persist_batches(self, df, table_name):
        records = df.to_dict(orient="records")
        try:
            for i in range(0, len(records), 4000):
                self.supabase.table(table_name).insert(records[i:i+4000]).execute()
        except Exception as e: logger.warning(f"DB Error: {e}")