import pandas as pd
import joblib
import uuid
import logging
import traceback
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class NASAPredictor:
    """
    I built this engine to calculate the Remaining Useful Life (RUL)
    of turbofan engines using the specific sensor features required by the model.
    """
    def __init__(self):
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except ImportError:
            self.supabase = None

        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "nasa_model.pkl"
        self.model = None
        
        # I mapped the columns to match the specific names the model expects
        # These are the standard names for the NASA CMAPSS FD001 dataset
        self.column_names = [
            'unit_id', 'time_in_cycles', 'setting_1', 'setting_2', 'setting_3',
            'sensor_1', 'sensor_2', 'sensor_3', 'sensor_4', 'sensor_5',
            'sensor_6', 'sensor_7', 'sensor_8', 'sensor_9', 'sensor_10',
            'sensor_11', 'sensor_12', 'sensor_13', 'sensor_14', 'sensor_15',
            'sensor_16', 'sensor_17', 'sensor_18', 'sensor_19', 'sensor_20',
            'sensor_21'
        ]
        
        self._load_model()

    def _load_model(self):
        """I load the predictive maintenance model from the serialized pickle file."""
        try:
            if self.model_path.exists():
                self.model = joblib.load(self.model_path)
                logger.info(f"✅ NASA Engine: Loaded from {self.model_path}")
            else:
                logger.warning(f"⚠️ NASA Engine: Model file missing at {self.model_path}")
        except Exception as e:
            logger.error(f"❌ NASA Load Error: {e}")

    async def predict_from_file(self, file):
        """I execute RUL predictions and handle the batch persistence to Supabase."""
        if not self.model:
            return {"success": False, "detail": "NASA engine not initialized"}

        try:
            # I read the whitespace-separated file and assign the required sensor names
            df_raw = pd.read_csv(file.file, sep=r'\s+', engine='python', header=None, names=self.column_names)
            
            # I perform the prediction. The model now finds the columns it expects.
            predictions = self.model.predict(df_raw)
            
            if predictions is None:
                raise ValueError("The model returned None. Verify feature alignment.")

            now_ts = datetime.now().isoformat()
            
            # I prepare the results for the database.
            # I am now using 'unit_id' to match the clean database schema.
            results_df = pd.DataFrame({
                'prediction_id': [str(uuid.uuid4()) for _ in range(len(df_raw))],
                'unit_id': df_raw['unit_id'].values.astype(int),
                'predicted_rul': predictions.astype(float),
                'timestamp': now_ts
            })

            # I use batching for the persistence layer to handle NASA telemetry files
            if self.supabase:
                self._persist_in_batches(results_df)

            return {
                "success": True,
                "units_processed": len(df_raw),
                "avg_rul": float(predictions.mean()),
                "status": "Operational"
            }

        except Exception as e:
            logger.error(f"❌ NASA Runtime Error: {traceback.format_exc()}")
            return {"success": False, "detail": str(e)}

    def _persist_in_batches(self, df: pd.DataFrame):
        """I process database insertions in chunks for high reliability."""
        table_name = "nasa_predictions"
        batch_size = 5000
        records = df.to_dict(orient='records')
        
        try:
            for i in range(0, len(records), batch_size):
                self.supabase.table(table_name).insert(records[i : i + batch_size]).execute()
            logger.info("✅ NASA Persistence Complete.")
        except Exception as e:
            logger.warning(f"⚠️ NASA Persistence Error: {e}")