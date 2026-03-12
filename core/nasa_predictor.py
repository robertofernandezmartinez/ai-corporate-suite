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


class NASAFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    This class must exist for joblib to unpickle the trained pipeline.
    Keep the name identical to the one used during training.
    """

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()
        df = df.apply(pd.to_numeric, errors="coerce").fillna(0)
        return df.values.astype(np.float64)


__main__.NASAFeatureEngineer = NASAFeatureEngineer


NASA_RAW_COLUMNS = [
    "unit_id",
    "time_in_cycles",
    "op_setting_1",
    "op_setting_2",
    "op_setting_3",
    "sensor_1",
    "sensor_2",
    "sensor_3",
    "sensor_4",
    "sensor_5",
    "sensor_6",
    "sensor_7",
    "sensor_8",
    "sensor_9",
    "sensor_10",
    "sensor_11",
    "sensor_12",
    "sensor_13",
    "sensor_14",
    "sensor_15",
    "sensor_16",
    "sensor_17",
    "sensor_18",
    "sensor_19",
    "sensor_20",
    "sensor_21",
]


def _load_nasa_dataframe(file) -> pd.DataFrame:
    filename = getattr(file, "filename", "") or ""
    file_ext = Path(filename).suffix.lower()

    try:
        file.file.seek(0)
    except Exception:
        pass

    if file_ext == ".txt":
        df = pd.read_csv(
            file.file,
            sep=r"\s+",
            header=None,
            engine="python"
        )

        df = df.dropna(axis=1, how="all")

        if df.shape[1] == 1:
            raise ValueError(
                "This looks like a NASA RUL labels file, not a raw telemetry file. "
                "Please upload train_FD001.txt or test_FD001.txt."
            )

        if df.shape[1] < len(NASA_RAW_COLUMNS):
            raise ValueError(
                f"Invalid NASA raw file: expected at least {len(NASA_RAW_COLUMNS)} columns, got {df.shape[1]}"
            )

        if df.shape[1] > len(NASA_RAW_COLUMNS):
            df = df.iloc[:, :len(NASA_RAW_COLUMNS)]

        df.columns = NASA_RAW_COLUMNS
        return df

    try:
        file.file.seek(0)
    except Exception:
        pass

    df = pd.read_csv(file.file, low_memory=False)

    if {"unit_id", "time_in_cycles"}.issubset(df.columns):
        return df

    if {"unit_id", "cycle"}.issubset(df.columns):
        df = df.rename(columns={"cycle": "time_in_cycles"})
        return df

    try:
        file.file.seek(0)
    except Exception:
        pass

    df_txt = pd.read_csv(
        file.file,
        sep=r"\s+",
        header=None,
        engine="python"
    )

    df_txt = df_txt.dropna(axis=1, how="all")

    if df_txt.shape[1] == 1:
        raise ValueError(
            "This looks like a NASA RUL labels file, not a raw telemetry file. "
            "Please upload train_FD001.txt or test_FD001.txt."
        )

    if df_txt.shape[1] >= len(NASA_RAW_COLUMNS):
        df_txt = df_txt.iloc[:, :len(NASA_RAW_COLUMNS)]
        df_txt.columns = NASA_RAW_COLUMNS
        return df_txt

    raise ValueError(
        "Could not parse uploaded NASA file. Please upload train_FD001.txt or test_FD001.txt."
    )


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
            df_raw = _load_nasa_dataframe(file)

            for col in ["unit_id", "time_in_cycles"]:
                if col not in df_raw.columns:
                    return {"success": False, "detail": f"Missing required column: {col}"}

            # Keep time_in_cycles because the trained pipeline expects it.
            X = df_raw.drop(columns=["unit_id"], errors="ignore")

            predicted_rul = self.pipeline.predict(X).astype(float)

            batch_id = str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc).isoformat()

            results_df = pd.DataFrame({
                "prediction_id": [str(uuid.uuid4()) for _ in range(len(df_raw))],
                "batch_id": batch_id,
                "created_at": now_ts,
                "unit_id": pd.to_numeric(df_raw["unit_id"], errors="coerce").fillna(0).astype(int),
                "time_in_cycles": pd.to_numeric(df_raw["time_in_cycles"], errors="coerce").fillna(0).astype(int),
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