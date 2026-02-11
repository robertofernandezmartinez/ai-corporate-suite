import pandas as pd
import joblib
from pathlib import Path
from db.supabase_client import get_supabase
from datetime import datetime
import traceback

class SmartPortPredictor:
    def __init__(self):
        models_dir = Path(__file__).parent.parent / "models"
        
        model_path = models_dir / "smartport_model.pkl"
        features_path = models_dir / "smartport_features.pkl"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        if not features_path.exists():
            raise FileNotFoundError(f"Features not found: {features_path}")
        
        print(f"Loading model from: {model_path}")
        
        self.pipeline = joblib.load(model_path)
        self.expected_features = joblib.load(features_path)
        
        print(f"Model loaded successfully: {type(self.pipeline)}")
        print(f"Expected features: {self.expected_features}")
        
        self.supabase = get_supabase()
        
        self.ACTION_MAP = {
            'CRITICAL': 'IMMEDIATE: Priority berthing & Tugboat standby.',
            'WARNING': 'PROACTIVE: Verify ETA and terminal capacity.',
            'NORMAL': 'ROUTINE: Follow standard operations.'
        }
    
    async def predict_from_file(self, file):
        try:
            print("Starting prediction process...")
            
            # Read CSV
            df = pd.read_csv(file.file)
            print(f"CSV loaded: {df.shape}")
            
            # Remove target if present
            X = df.drop(columns=['delay_flag'], errors='ignore')
            print(f"Features shape: {X.shape}")
            
            # Align columns
            for col in self.expected_features:
                if col not in X.columns:
                    X[col] = 0
            
            X = X[self.expected_features]
            print(f"Aligned features shape: {X.shape}")
            
            # Predict
            print("Calling predict_proba...")
            probs = self.pipeline.predict_proba(X)[:, 1]
            print(f"Predictions generated: {len(probs)}")
            
            # Create results
            results = pd.DataFrame({
                'vessel_index': df.index,
                'risk_score': probs,
                'risk_level': pd.Series(probs).apply(
                    lambda x: 'CRITICAL' if x >= 0.90 else ('WARNING' if x >= 0.70 else 'NORMAL')
                ),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            results['recommended_action'] = results['risk_level'].map(self.ACTION_MAP)
            
            # Save to Supabase in BATCHES
            print("Saving to Supabase in batches...")
            records = results.to_dict('records')
            
            # Add prediction_id
            for record in records:
                record['prediction_id'] = f"SP_{datetime.now().strftime('%Y%m%d%H%M%S')}_{record['vessel_index']}"
            
            # Insert in batches of 1000
            batch_size = 1000
            total_batches = (len(records) + batch_size - 1) // batch_size
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                self.supabase.table('smartport_alerts').insert(batch).execute()
                print(f"Batch {i//batch_size + 1}/{total_batches} saved")
            
            print("All batches saved to Supabase")
            
            # Return summary
            distribution = results['risk_level'].value_counts().to_dict()
            
            return {
                "success": True,
                "predictions_generated": len(results),
                "distribution": distribution,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"ERROR in predict_from_file: {e}")
            print(traceback.format_exc())
            raise
