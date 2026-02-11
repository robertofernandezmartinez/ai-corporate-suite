import os
import gspread
from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

app = FastAPI(title="AI Corporate Suite API")

# Initialize Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@app.get("/")
def read_root():
    return {"status": "online", "message": "AI Corporate Suite API is ready"}

@app.get("/tracking/stats")
def get_tracking_stats():
    """Returns the total number of rows in the tracking table."""
    try:
        response = supabase.table("port_tracking_v2").select("*", count="exact").limit(1).execute()
        return {
            "status": "success",
            "total_rows_in_db": response.count,
            "table_active": "port_tracking_v2"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tracking/ship/{ship_name}")
def get_ship_data(ship_name: str):
    """Search for the last 5 movements of a specific ship."""
    try:
        response = supabase.table("port_tracking_v2") \
            .select("*") \
            .order("updated", desc=True) \
            .limit(5) \
            .execute()
        return {"ship": ship_name, "data": response.data}
    except Exception as e:
        return {"error": str(e)}

@app.post("/sheets/report")
def append_prediction_report(data: dict):
    """Sends a report row to the SmartPort spreadsheet."""
    try:
        import datetime
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Path to service account (one level up from /app)
        json_path = os.path.join(os.path.dirname(__file__), '..', 'service_account.json')
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        
        # MATCHING YOUR .ENV NAME:
        sheet_id = os.getenv("SMARTPORT_SPREADSHEET_ID")
        sheet = client.open_by_key(sheet_id).sheet1
        
        # Prepare row for SmartPort
        new_row = [
            f"PRED-{datetime.datetime.now().strftime('%M%S')}", 
            str(datetime.datetime.now()),
            data.get("vessel_id", "Unknown"),
            data.get("risk_score", 0),
            "HIGH" if data.get("risk_score", 0) > 0.5 else "NORMAL",
            "Follow standard protocol",
            "Pending Review"
        ]
        
        sheet.append_row(new_row)
        return {"status": "success", "message": "Report added to SmartPort Sheet"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))