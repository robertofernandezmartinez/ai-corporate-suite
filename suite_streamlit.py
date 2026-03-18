import os
import requests
import streamlit as st
from db.supabase_client import get_supabase
from ui_theme import apply_suite_theme, render_page_header

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="AI Corporate Suite",
    page_icon="🧠",
    layout="wide"
)

apply_suite_theme()

# --- SIDEBAR: OPERATIONAL CONTROL ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg", width=50)
    st.title("Control Center")
    st.markdown("---")
    
    st.subheader("🔔 Real-Time Alerts")
    st.info(
        "Connect to our **Telegram Bot** to receive proactive push notifications "
        "when the AI engines detect critical industrial risks."
    )
    # Reemplaza con tu link real de Telegram
    st.link_button("🚀 Open Telegram Bot", "https://t.me/TU_BOT_USERNAME")
    
    st.markdown("---")
    st.caption("🤖 Powered by Claude 3 AI")
    st.caption("🚀 Deployed on Railway Cloud")

# ==========================================
# API & METRICS LOGIC
# ==========================================
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
        per_module[name] = {"batches": batches, "predictions": predictions, "last_run": last_run}
    global_last_run = max(last_runs) if last_runs else None
    return total_batches, total_predictions, global_last_run, per_module

# EXECUTION
ok, api_status = api_healthcheck(API_BASE_URL)
total_batches, total_predictions, global_last_run, per_module = fetch_global_metrics()

# ==========================================
# MAIN UI CONTENT
# ==========================================
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
<p>The suite integrates three machine learning modules into a single operational environment:</p>
<ul>
<li><strong>SmartPort</strong> — Maritime operational risk monitoring</li>
<li><strong>Stockout</strong> — Retail inventory stockout intelligence</li>
<li><strong>NASA RUL</strong> — Predictive maintenance for turbofan engines</li>
</ul>
<p>Each module supports manual uploads, API-driven inference, cloud persistence, and proactive alerting via Telegram.</p>
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
    st.markdown('<div class="suite-card"><h3>🚢 SmartPort</h3><p>Maritime operational risk.</p></div>', unsafe_allow_html=True)
    st.metric("Batches", per_module["SmartPort"]["batches"])
    st.metric("Predictions", per_module["SmartPort"]["predictions"])
    st.caption(f"Last run: {per_module['SmartPort']['last_run'] if per_module['SmartPort']['last_run'] else 'N/A'}")

with c2:
    st.markdown('<div class="suite-card"><h3>📦 Stockout</h3><p>Retail stockout risk monitoring.</p></div>', unsafe_allow_html=True)
    st.metric("Batches", per_module["Stockout"]["batches"])
    st.metric("Predictions", per_module["Stockout"]["predictions"])
    st.caption(f"Last run: {per_module['Stockout']['last_run'] if per_module['Stockout']['last_run'] else 'N/A'}")

with c3:
    st.markdown('<div class="suite-card"><h3>🛠️ NASA RUL</h3><p>Predictive maintenance.</p></div>', unsafe_allow_html=True)
    st.metric("Batches", per_module["NASA"]["batches"])
    st.metric("Predictions", per_module["NASA"]["predictions"])
    st.caption(f"Last run: {per_module['NASA']['last_run'] if per_module['NASA']['last_run'] else 'N/A'}")

st.subheader("How the Suite Works")
st.markdown(
    """
<div class="suite-card">
<p><strong>Manual & API Uploads</strong><br>
Send datasets via UI or FastAPI. The system runs inference, validates schema (Guardrails), and triggers <strong>Telegram Alerts</strong> if critical risks are found.</p>
<p><strong>Persistence & Batch Logic</strong><br>
Results are stored in <strong>Supabase (PostgreSQL)</strong>. Each run is isolated by a <code>batch_id</code> to allow historical auditing and comparison.</p>
</div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Suggested Navigation")
st.markdown(
    """
1. Open **Upload Center** to run a manual prediction batch.  
2. Connect to the **Telegram Bot** (Sidebar) to receive real-time alerts.
3. Inspect results in **SmartPort**, **Stockout**, or **NASA** dashboards.
"""
)

st.caption("AI Corporate Suite | Operational ML Platform")