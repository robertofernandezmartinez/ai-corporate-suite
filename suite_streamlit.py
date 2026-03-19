import os
import requests
import streamlit as st
from db.supabase_client import get_supabase
from ui_theme import apply_suite_theme, render_page_header

# --- Page Configuration ---
# Must be the first Streamlit command to ensure correct rendering
st.set_page_config(
    page_title="AI Corporate Suite", 
    page_icon="🧠", 
    layout="wide"
)

# Apply global CSS and design theme
apply_suite_theme()

# Load API Backend URL from environment variables (defaults to localhost for dev)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# --- Backend Helper Functions ---

def api_healthcheck(base_url: str):
    """Verifies if the FastAPI backend is operational and reachable."""
    try:
        r = requests.get(f"{base_url}/", timeout=10)
        return (True, "Online") if r.status_code == 200 else (False, f"Error {r.status_code}")
    except Exception: 
        return False, "Offline"

def fetch_global_metrics():
    """Retrieves high-level statistics from Supabase across all ML modules."""
    module_tables = {
        "SmartPort": "smartport_predictions", 
        "Stockout": "stockout_predictions", 
        "NASA": "nasa_predictions"
    }
    stats = {"total_b": 0, "total_p": 0, "per_m": {}}
    
    try:
        sb = get_supabase()
        for name, table in module_tables.items():
            # Query data to calculate batch count and total predictions
            res = sb.table(table).select("batch_id").execute()
            data = res.data or []
            
            count = len(data)
            # Use a set to identify unique batch executions
            batches = len(set(r["batch_id"] for r in data if r.get("batch_id")))
            
            # Aggregate global metrics
            stats["total_p"] += count
            stats["total_b"] += batches
            stats["per_m"][name] = {"p": count, "b": batches}
    except Exception: 
        pass # Silent fail to keep UI responsive even if DB connection fluctuates
        
    return stats

# --- UI Layout Implementation ---

# Render the dynamic header with technical tags
render_page_header(
    "🧠 AI Corporate Suite",
    "Unified operational AI platform for maritime risk, retail intelligence, and predictive maintenance.",
    tags=["FastAPI", "Streamlit", "Supabase", "Railway"]
)

# --- Operational Alerts Notification ---
# Demonstrates the integration with the Telegram bot for push notifications
st.success(
    "🤖 **Proactive Monitoring Active:** Critical industrial risks are automatically "
    "routed to the Administrator's Telegram Terminal in real-time."
)

# --- Metrics Dashboard Section ---
ok, status = api_healthcheck(API_BASE_URL)
stats = fetch_global_metrics()

# Main metric columns for an executive overview
col1, col2, col3 = st.columns(3)
col1.metric("API Status", status, delta="Operational" if ok else "Check Logs")
col2.metric("Total Batches", stats["total_b"])
col3.metric("Total Predictions", stats["total_p"])

st.markdown("---")
st.subheader("Module Status")

# Detailed module breakdown can follow here...