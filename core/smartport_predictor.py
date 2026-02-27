import pandas as pd
import numpy as np
import joblib
import traceback
import uuid
import logging
from pathlib import Path
from datetime import datetime
from sklearn.base import BaseEstimator, TransformerMixin
import __main__

logger = logging.getLogger(__name__)

class SmartPortFeatureEngineer(BaseEstimator, TransformerMixin):
    """I defined this class to handle the vessel telemetry engineering logic."""
    def __init__(self):
        self.selected_features = [
            'day_of_week', 'rolling_mean_sog', 'hdg', 'movement_stability',
            'cog', 'speed_delta', 'heading_change', 'imo_te',
            'reporting_interval_min', 'time_since_last_position_min', 'arr_port_FIHEL'
        ]

    def fit(self, X, y=None): return self

    def transform(self, X):
        df = X.copy()
        ts_col = 'updated_ts' if 'updated_ts' in df.columns else 'timestamp'
        if ts_col in df.columns:
            df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')
            df['day_of_week'] = df[ts_col].dt.dayofweek
        
        # Default values for missing features to avoid model crashes
        for col in self.selected_features:
            if col not in df.columns: df[col] = 0.0
        
        return df[self.selected_features].fillna(0).values.astype(np.float64)

__main__.SmartPortFeatureEngineer = SmartPortFeatureEngineer

class SmartPortPredictor:
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except ImportError:
            self.supabase = None

        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "smartport_model.pkl"
        self.pipeline = None
        self._load_engine()

    def _load_engine(self):
        """I load the SmartPort pipeline from the models folder."""
        try:
            if self.model_path.exists():
                self.pipeline = joblib.load(self.model_path)
                logger.info(f"✅ SmartPort Engine: Loaded")
        except Exception as e:
            logger.error(f"❌ SmartPort Load Error: {e}")

    async def predict_from_file(self, file):
        """I process vessel data and save results into the consistent predictions table."""
        if not self.pipeline:
            return {"success": False, "detail": "Engine not initialized"}

        try:
            df_raw = pd.read_csv(file.file, low_memory=False)
            probabilities = self.pipeline.predict_proba(df_raw)[:, 1]
            
            now_ts = datetime.now().isoformat()
            results_df = pd.DataFrame({
                'prediction_id': [str(uuid.uuid4()) for _ in range(len(df_raw))],
                'vessel_index': range(len(df_raw)),
                'risk_score': probabilities.astype(float),
                'risk_level': ['CRITICAL' if p >= 0.80 else 'NORMAL' for p in probabilities],
                'timestamp': now_ts
            })

            if self.supabase:
                self._persist_batches(results_df)

            return {"success": True, "processed_records": len(df_raw)}
        except Exception as e:
            logger.error(f"❌ SmartPort Runtime Error: {traceback.format_exc()}")
            return {"success": False, "detail": str(e)}

    def _persist_batches(self, df: pd.DataFrame):
        table_name = "smartport_predictions"
        batch_size = 4000
        records = df.to_dict(orient='records')
        try:
            for i in range(0, len(records), batch_size):
                self.supabase.table(table_name).insert(records[i : i + batch_size]).execute()
            logger.info("✅ SmartPort Persistence Complete.")
        except Exception as e:
            logger.warning(f"⚠️ Persistence Error: {e}")