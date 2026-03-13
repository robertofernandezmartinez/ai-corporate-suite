import os
import requests
import streamlit as st
from db.supabase_client import get_supabase
from ui_theme import apply_suite_theme, render_page_header


st.set_page_config(
    page_title="AI Corporate Suite",
    page_icon="🧠",
    layout="wide"
)

apply_suite_theme()

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

render_page_header(
    "🧠 AI Corporate Suite",
    "Unified operational AI platform for maritime risk, retail inventory intelligence, and predictive maintenance.",
    tags=["FastAPI", "Streamlit", "Supabase", "Railway"]
)

hero_left, hero_right = st.columns([1.5, 1])

with hero_left:
    st.markdown(
        """
<div class="suite-card">
<h3>Platform Overview</h3>
<p>
The suite integrates three machine learning modules into a single operational environment:
</p>
<ul>
<li><strong>SmartPort</strong> — Maritime operational risk monitoring</li>
<li><strong>Stockout</strong> — Retail inventory stockout intelligence</li>
<li><strong>NASA RUL</strong> — Predictive maintenance for turbofan engines</li>
</ul>
<p>
Each module supports manual uploads, API-driven inference, cloud persistence in Supabase, and batch-based dashboard analysis.
</p>
</div>
        """,
        unsafe_allow_html=True,
    )

with hero_right:
    status_type = "success" if ok else "error"
    message = f"API Status: {api_status}"
    getattr(st, status_type)(message)
    st.info(f"API Base URL: {API_BASE_URL}")

st.subheader("Global Metrics")

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Total Stored Batches", total_batches)
with m2:
    st.metric("Total Stored Predictions", total_predictions)
with m3:
    st.metric("Last Platform Run", global_last_run if global_last_run else "N/A")

st.subheader("Module Status")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        f"""
<div class="suite-card">
<h3>🚢 SmartPort</h3>
<p>Maritime operational risk prediction.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.metric("Batches", per_module["SmartPort"]["batches"])
    st.metric("Predictions", per_module["SmartPort"]["predictions"])
    st.caption(f"Last run: {per_module['SmartPort']['last_run'] if per_module['SmartPort']['last_run'] else 'N/A'}")

with c2:
    st.markdown(
        f"""
<div class="suite-card">
<h3>📦 Stockout</h3>
<p>Retail stockout risk and exposure monitoring.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.metric("Batches", per_module["Stockout"]["batches"])
    st.metric("Predictions", per_module["Stockout"]["predictions"])
    st.caption(f"Last run: {per_module['Stockout']['last_run'] if per_module['Stockout']['last_run'] else 'N/A'}")

with c3:
    st.markdown(
        f"""
<div class="suite-card">
<h3>🛠️ NASA RUL</h3>
<p>Predictive maintenance and remaining useful life estimation.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.metric("Batches", per_module["NASA"]["batches"])
    st.metric("Predictions", per_module["NASA"]["predictions"])
    st.caption(f"Last run: {per_module['NASA']['last_run'] if per_module['NASA']['last_run'] else 'N/A'}")

st.subheader("How the Suite Works")
st.markdown(
    """
<div class="suite-card">
<p><strong>Manual Uploads</strong><br>
Use the Upload Center to send a dataset to the FastAPI backend. The backend runs model inference and stores results in Supabase as a new batch.</p>

<p><strong>Automatic Demo Loading</strong><br>
The platform includes automation scripts that can populate the dashboards with demonstration data.</p>

<p><strong>Automatic Cleanup</strong><br>
Old batches can be removed automatically to control storage growth.</p>

<p><strong>Batch Logic</strong><br>
Manual uploads and automated runs coexist. Each execution generates a unique <code>batch_id</code>, so historical runs are not overwritten.</p>
</div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Suggested Navigation")
st.markdown(
    """
1. Open **Upload Center** to run a manual prediction batch  
2. Go to **SmartPort**, **Stockout**, or **NASA** to inspect results  
3. Use batch selectors inside each dashboard to compare historical runs  
4. Use cleanup controls when you want a fresh demo environment
"""
)

st.subheader("Deployment")
st.markdown(
    """
<div class="suite-card">
<p>The platform is deployed as two separated services on Railway:</p>
<ul>
<li><strong>UI</strong> — Streamlit dashboards</li>
<li><strong>API</strong> — FastAPI inference backend</li>
</ul>
<p>Predictions are persisted in <strong>Supabase</strong>.</p>
</div>
    """,
    unsafe_allow_html=True,
)

st.caption("AI Corporate Suite | Operational ML Platform")