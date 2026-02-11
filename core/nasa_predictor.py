import pandas as pd
import joblib
from pathlib import Path
from db.supabase_client import get_supabase
from datetime import datetime
import traceback

class NASAPredictor:
    def __init__(self):
        models_dir = Path(__file__).parent.parent / "models"
        
        model_path = models_dir / "nasa_model.pkl"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        print(f"Loading NASA model from: {model_path}")
        
        # Load trained pipeline
        self.pipeline = joblib.load(model_path)
        
        print(f"NASA model loaded successfully: {type(self.pipeline)}")
        
        # Expected features based on NASA training
        self.expected_features = [
            'time_in_cycles',
            'sensor_11',
            'sensor_4',
            'sensor_12',
            'sensor_7',
            'sensor_15',
            'sensor_21',
            'sensor_20'
        ]
        
        print(f"Expected features: {self.expected_features}")
        
        self.supabase = get_supabase()
    
    async def predict_from_file(self, file):
        """
        Process uploaded engine data and predict RUL
        """
        try:
            print("Starting NASA RUL prediction process...")
            
            # Read TXT/CSV file
            df = pd.read_csv(file.file, delim_whitespace=True, header=None)
            print(f"File loaded: {df.shape}")
            
            # Assign column names (NASA format)
            n_cols = df.shape[1]
            n_sensors = n_cols - 5
            columns = (
                ['unit_number', 'time_in_cycles'] +
                [f'op_setting_{i}' for i in range(1, 4)] +
                [f'sensor_{i}' for i in range(1, n_sensors + 1)]
            )
            df.columns = columns
            
            print(f"Columns assigned: {df.columns.tolist()[:5]}...")
            
            # Extract features
            X = df[self.expected_features]
            print(f"Features shape: {X.shape}")
            
            # Predict RUL
            print("Calling predict...")
            rul_predictions = self.pipeline.predict(X)
            print(f"Predictions generated: {len(rul_predictions)}")
            
            # Create results
            results = pd.DataFrame({
                'unit_number': df['unit_number'],
                'time_in_cycles': df['time_in_cycles'],
                'predicted_rul': rul_predictions,
                'rul_category': pd.Series(rul_predictions).apply(self._categorize_rul),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Save to Supabase in batches
            print("Saving to Supabase in batches...")
            records = results.to_dict('records')
            
            # Add prediction_id
            for record in records:
                record['prediction_id'] = f"NASA_{datetime.now().strftime('%Y%m%d%H%M%S')}_{record['unit_number']}_{record['time_in_cycles']}"
            
            # Insert in batches of 1000
            batch_size = 1000
            total_batches = (len(records) + batch_size - 1) // batch_size
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                self.supabase.table('nasa_rul_predictions').insert(batch).execute()
                print(f"Batch {i//batch_size + 1}/{total_batches} saved")
            
            print("All batches saved to Supabase")
            
            # Return summary
            category_dist = results['rul_category'].value_counts().to_dict()
            avg_rul = float(results['predicted_rul'].mean())
            
            return {
                "success": True,
                "predictions_generated": len(results),
                "engines_analyzed": int(df['unit_number'].nunique()),
                "average_rul": round(avg_rul, 2),
                "category_distribution": category_dist,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"ERROR in predict_from_file: {e}")
            print(traceback.format_exc())
            raise
    
    def _categorize_rul(self, rul):
        """Categorize RUL into maintenance urgency levels"""
        if rul < 50:
            return 'CRITICAL'
        elif rul < 100:
            return 'WARNING'
        else:
            return 'NORMAL'
