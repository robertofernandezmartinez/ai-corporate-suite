import os
import requests
import streamlit as st
from db.supabase_client import get_supabase


st.set_page_config(
    page_title="AI Corporate Suite",
    page_icon="🧠",
    layout="wide"
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def api_healthcheck(base_url: str):
    try:
        r = requests.get(f"{base_url}/", timeout=10)
        if r.status_code == 200:
            return True, "Online"
        return False, f"API returned {r.status_code}"
    except Exception:
        return False, "Offline"


def fetch_table_metrics(table_name: str):
    try:
        supabase = get_supabase()
        resp = supabase.table(table_name).select("batch_id,created_at").execute()
        rows = resp.data or []

        total_predictions = len(rows)
        total_batches = len(set(r["batch_id"] for r in rows if r.get("batch_id"))) if rows else 0
        last_run = max((r["created_at"] for r in rows if r.get("created_at")), default=None)

        return total_batches, total_predictions, last_run
    except Exception:
        return 0, 0, None


def fetch_global_metrics():
    module_tables = {
        "SmartPort": "smartport_predictions",
        "Stockout": "stockout_predictions",
        "NASA": "nasa_predictions",
    }

    total_batches = 0
    total_predictions = 0
    last_runs = []

    per_module = {}

    for name, table in module_tables.items():
        batches, predictions, last_run = fetch_table_metrics(table)
        total_batches += batches
        total_predictions += predictions
        if last_run:
            last_runs.append(last_run)

        per_module[name] = {
            "batches": batches,
            "predictions": predictions,
            "last_run": last_run,
        }

    global_last_run = max(last_runs) if last_runs else None

    return total_batches, total_predictions, global_last_run, per_module


ok, api_status = api_healthcheck(API_BASE_URL)
total_batches, total_predictions, global_last_run, per_module = fetch_global_metrics()

st.title("🧠 AI Corporate Suite")
st.caption("Unified operational AI platform for maritime risk, retail inventory intelligence, and predictive maintenance.")

st.markdown("---")

hero_left, hero_right = st.columns([1.5, 1])

with hero_left:
    st.subheader("Platform Overview")
    st.markdown(
        """
The suite integrates three machine learning modules into a single operational environment:

- **SmartPort** — Maritime operational risk monitoring
- **Stockout** — Retail inventory stockout intelligence
- **NASA RUL** — Predictive maintenance for turbofan engines

Each module supports:
- manual uploads
- API-driven inference
- cloud persistence in Supabase
- batch-based dashboard analysis
"""
    )

with hero_right:
    st.subheader("System Status")
    if ok:
        st.success(f"API Status: {api_status}")
    else:
        st.error(f"API Status: {api_status}")

    st.info(f"API Base URL: {API_BASE_URL}")

st.markdown("---")

st.subheader("Global Metrics")

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Total Stored Batches", total_batches)

with m2:
    st.metric("Total Stored Predictions", total_predictions)

with m3:
    st.metric("Last Platform Run", global_last_run if global_last_run else "N/A")

st.markdown("---")

st.subheader("Module Status")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 🚢 SmartPort")
    st.write("Maritime operational risk prediction.")
    st.metric("Batches", per_module["SmartPort"]["batches"])
    st.metric("Predictions", per_module["SmartPort"]["predictions"])
    st.caption(f"Last run: {per_module['SmartPort']['last_run'] if per_module['SmartPort']['last_run'] else 'N/A'}")

with c2:
    st.markdown("### 📦 Stockout")
    st.write("Retail stockout risk and exposure monitoring.")
    st.metric("Batches", per_module["Stockout"]["batches"])
    st.metric("Predictions", per_module["Stockout"]["predictions"])
    st.caption(f"Last run: {per_module['Stockout']['last_run'] if per_module['Stockout']['last_run'] else 'N/A'}")

with c3:
    st.markdown("### 🛠️ NASA RUL")
    st.write("Predictive maintenance and remaining useful life estimation.")
    st.metric("Batches", per_module["NASA"]["batches"])
    st.metric("Predictions", per_module["NASA"]["predictions"])
    st.caption(f"Last run: {per_module['NASA']['last_run'] if per_module['NASA']['last_run'] else 'N/A'}")

st.markdown("---")

st.subheader("How the Suite Works")
st.markdown(
    """
**Manual Uploads**  
Use the Upload Center to send a dataset to the FastAPI backend.  
The backend runs model inference and stores results in Supabase as a new batch.

**Automatic Demo Loading**  
The platform includes automation scripts that can populate the dashboards with demonstration data.

**Automatic Cleanup**  
Old batches can be removed automatically to control storage growth.

**Batch Logic**  
Manual uploads and automated runs coexist.  
Each execution generates a unique `batch_id`, so historical runs are not overwritten.
"""
)

st.markdown("---")

st.subheader("Suggested Navigation")
st.markdown(
    """
1. Open **Upload Center** to run a manual prediction batch  
2. Go to **SmartPort**, **Stockout**, or **NASA** to inspect results  
3. Use batch selectors inside each dashboard to compare historical runs  
4. Use cleanup controls when you want a fresh demo environment
"""
)

st.markdown("---")

st.subheader("Deployment")
st.markdown(
    """
The platform is deployed as two separated services on Railway:

- **UI** — Streamlit dashboards
- **API** — FastAPI inference backend

Predictions are persisted in **Supabase**.
"""
)

st.caption("AI Corporate Suite | Operational ML Platform")