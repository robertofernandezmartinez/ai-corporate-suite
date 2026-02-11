import pandas as pd
import joblib
from pathlib import Path
from db.supabase_client import get_supabase
from datetime import datetime
import traceback

class StockoutPredictor:
    def __init__(self):
        models_dir = Path(__file__).parent.parent / "models"
        
        model_path = models_dir / "stockout_model.pkl"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        print(f"Loading Stockout model from: {model_path}")
        
        self.pipeline = joblib.load(model_path)
        
        print(f"Stockout model loaded successfully: {type(self.pipeline)}")
        
        self.supabase = get_supabase()
    
    async def predict_from_file(self, file):
        """
        Process uploaded inventory CSV and predict stockout risk
        """
        try:
            print("Starting Stockout prediction process...")
            
            # Read CSV
            df = pd.read_csv(file.file)
            print(f"CSV loaded: {df.shape}")
            
            # Rename columns (same as training)
            df = df.rename(columns={
                "Date": "date",
                "Store ID": "store_id",
                "Product ID": "product_id",
                "Category": "category",
                "Region": "region",
                "Inventory Level": "inventory_level",
                "Units Sold": "units_sold",
                "Units Ordered": "units_ordered",
                "Demand Forecast": "demand_forecast",
                "Price": "price",
                "Discount": "discount",
                "Weather Condition": "weather",
                "Holiday/Promotion": "holiday_promo",
                "Competitor Pricing": "competitor_pricing",
                "Seasonality": "seasonality",
            })
            
            # Convert data types
            df['holiday_promo'] = df['holiday_promo'].astype('category')
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Drop target if present
            X = df.drop(columns=['stockout_14d'], errors='ignore')
            
            print(f"Features shape: {X.shape}")
            
            # Predict
            print("Calling predict...")
            preds = self.pipeline.predict(X)
            probs = self.pipeline.predict_proba(X)[:, 1]
            
            print(f"Predictions generated: {len(preds)}")
            
            # Create results
            results = pd.DataFrame({
                'product_id': df['product_id'] if 'product_id' in df.columns else df.index,
                'store_id': df['store_id'] if 'store_id' in df.columns else 'UNKNOWN',
                'stockout_risk_score': probs,
                'stockout_predicted': preds,
                'risk_level': pd.Series(probs).apply(
                    lambda x: 'HIGH' if x >= 0.70 else ('MEDIUM' if x >= 0.40 else 'LOW')
                ),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Save to Supabase in batches
            print("Saving to Supabase in batches...")
            records = results.to_dict('records')
            
            for i, record in enumerate(records):
                record['prediction_id'] = f"ST_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}_{record['product_id']}"

            batch_size = 1000
            total_batches = (len(records) + batch_size - 1) // batch_size
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                self.supabase.table('stockout_predictions').insert(batch).execute()
                print(f"Batch {i//batch_size + 1}/{total_batches} saved")
            
            print("All batches saved to Supabase")
            
            # Return summary
            distribution = results['risk_level'].value_counts().to_dict()
            
            return {
                "success": True,
                "predictions_generated": len(results),
                "distribution": distribution,
                "high_risk_products": int((results['risk_level'] == 'HIGH').sum()),
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"ERROR in predict_from_file: {e}")
            print(traceback.format_exc())
            raise
