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


# ============================================================
# Feature Engineering Class (MUST match training definition)
# ============================================================
class StockoutFeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.cat_cols = [
            'store_id', 'category', 'region', 'weather', 'holiday_promo',
            'seasonality', 'month', 'day_of_week', 'product_id'
        ]
        self.num_cols = [
            'inventory_level', 'units_sold', 'price', 'discount',
            'competitor_pricing', 'is_weekend'
        ]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()

        # Map PRO dataset columns -> internal schema
        mapping = {
            'Date': 'date',
            'Store ID': 'store_id',
            'Product ID': 'product_id',
            'Category': 'category',
            'Region': 'region',
            'Inventory Level': 'inventory_level',
            'Units Sold': 'units_sold',
            'Units Ordered': 'units_ordered',
            'Price': 'price',
            'Discount': 'discount',
            'Weather Condition': 'weather',
            'Holiday/Promotion': 'holiday_promo',
            'Competitor Pricing': 'competitor_pricing',
            'Seasonality': 'seasonality'
        }
        df = df.rename(columns=mapping)

        # Time features
        if 'date' in df.columns:
            date_dt = pd.to_datetime(df['date'], errors='coerce', dayfirst=True)
            df['month'] = date_dt.dt.month.astype('Int64').astype(str).fillna('Unknown')
            df['day_of_week'] = date_dt.dt.dayofweek.astype('Int64').astype(str).fillna('Unknown')
            df['is_weekend'] = date_dt.dt.dayofweek.isin([5, 6]).astype(float)
        else:
            df['month'] = 'Unknown'
            df['day_of_week'] = 'Unknown'
            df['is_weekend'] = 0.0

        # Enforce categorical schema
        for col in self.cat_cols:
            if col not in df.columns:
                df[col] = 'Unknown'
            df[col] = df[col].astype(str)

        # Enforce numeric schema (critical to avoid isnan/imputer errors)
        for col in self.num_cols:
            if col not in df.columns:
                df[col] = 0.0

            # Clean typical numeric-as-string issues (commas, spaces)
            if df[col].dtype == object:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(',', '', regex=False)
                    .str.strip()
                )

            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        return df[self.cat_cols + self.num_cols]


# Fix for models trained in __main__ (notebook/script)
__main__.StockoutFeatureEngineer = StockoutFeatureEngineer


# ============================================================
# Stockout Predictor
# ============================================================
class StockoutPredictor:
    def __init__(self):
        # Supabase init (safe)
        try:
            from db.supabase_client import get_supabase
            self.supabase = get_supabase()
        except Exception as e:
            logger.warning(f"Supabase not available: {e}")
            self.supabase = None

        # Find model robustly (avoid fragile parent.parent assumptions)
        current_file = Path(__file__).resolve()
        self.model_path = None
        for parent in [current_file.parent] + list(current_file.parents):
            candidate = parent / "models" / "stockout_model.pkl"
            if candidate.exists():
                self.model_path = candidate
                break

        if self.model_path is None:
            logger.error("❌ Stockout Init Error: stockout_model.pkl not found under any parent /models/")
            self.pipeline = None
            return

        try:
            self.pipeline = joblib.load(self.model_path)
            logger.info(f"✅ Stockout Engine loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"❌ Stockout Engine Load Error: {e}")
            logger.error(traceback.format_exc())
            self.pipeline = None

    def _get_risk_level(self, score: float) -> str:
        if score >= 0.80:
            return 'CRITICAL'
        if score >= 0.50:
            return 'HIGH'
        if score >= 0.20:
            return 'MEDIUM'
        return 'LOW'

    async def predict_from_file(self, file):
        if not self.pipeline:
            return {"success": False, "detail": "Engine not initialized"}

        try:
            # Read raw CSV (do NOT pre-subset columns; pipeline expects raw)
            df_raw = pd.read_csv(file.file, low_memory=False)

            # Predict
            probabilities = self.pipeline.predict_proba(df_raw)[:, 1].astype(float)

            # Financial impact proxy (Risk * Price * Velocity)
            # Supports both PRO-style and already-normalized columns
            price = pd.to_numeric(
                df_raw.get('Price', df_raw.get('price', 0)),
                errors='coerce'
            ).fillna(0.0)

            velocity = pd.to_numeric(
                df_raw.get('Units Sold', df_raw.get('units_sold', 0)),
                errors='coerce'
            ).fillna(0.0)

            impact_score = (probabilities * price * velocity).astype(float)

            now_ts = datetime.now().isoformat(timespec="seconds")

            product_id_series = df_raw.get('Product ID', df_raw.get('product_id', 'Unknown'))
            if not isinstance(product_id_series, (pd.Series, np.ndarray, list)):
                product_id_series = [product_id_series] * len(df_raw)

            results_df = pd.DataFrame({
                'prediction_id': [str(uuid.uuid4()) for _ in range(len(df_raw))],
                'product_id': pd.Series(product_id_series).astype(str),
                'risk_score': probabilities,
                'risk_level': [self._get_risk_level(p) for p in probabilities],
                'financial_impact': impact_score,
                'timestamp': [now_ts for _ in range(len(df_raw))]
            })

            # Persist to NEW table name: stockout_predictions (non-blocking, batched)
            if self.supabase:
                self._persist_to_db(results_df)

            return {
                "success": True,
                "processed_records": len(df_raw),
                "total_exposure": float(results_df['financial_impact'].sum()),
                "risk_summary": results_df['risk_level'].value_counts().to_dict(),
                "top_alerts": results_df.sort_values(by='financial_impact', ascending=False).head(10).to_dict('records')
            }

        except Exception as e:
            logger.error(f"❌ Stockout Runtime Error:\n{traceback.format_exc()}")
            return {"success": False, "detail": str(e)}

    def _persist_to_db(self, df: pd.DataFrame):
        table_name = "stockout_predictions"
        batch_size = 5000
        records = df.to_dict(orient='records')

        try:
            for i in range(0, len(records), batch_size):
                self.supabase.table(table_name).insert(records[i:i + batch_size]).execute()
            logger.info(f"✅ Batch persistence successful for {table_name}")
        except Exception as e:
            logger.error(f"⚠️ Persistence Warning: {e}")