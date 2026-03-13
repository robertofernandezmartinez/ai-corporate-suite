import os
import requests
import streamlit as st
from db.supabase_client import get_supabase
from ui_theme import apply_suite_theme, render_page_header


st.set_page_config(
    page_title="Upload Center | AI Corporate Suite",
    page_icon="⬆️",
    layout="wide",
)

apply_suite_theme()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

MODULES = {
    "SmartPort (Maritime Risk)": {
        "endpoint": "/smartport/upload",
        "help": "Upload vessel tracking CSV (AIS-like telemetry).",
        "accepted": [".csv"],
        "table": "smartport_predictions",
        "description": "Maritime operational risk prediction for vessel activity and exposure monitoring.",
        "demo_file": "tracking_db_demo.csv",
    },
    "Stockout (Retail Risk)": {
        "endpoint": "/stockout/upload",
        "help": "Upload retail inventory CSV (PRO schema).",
        "accepted": [".csv"],
        "table": "stockout_predictions",
        "description": "Retail stockout probability and financial exposure prediction.",
        "demo_file": "retail_store_inventory_PRO.csv",
    },
    "NASA (RUL Prediction)": {
        "endpoint": "/nasa/upload",
        "help": "Upload NASA CMAPSS raw telemetry TXT file.",
        "accepted": [".txt", ".csv"],
        "table": "nasa_predictions",
        "description": "Remaining Useful Life prediction for turbofan engines.",
        "demo_file": "train_FD001.txt",
    },
}


def api_healthcheck(base_url: str) -> tuple[bool, str]:
    try:
        r = requests.get(f"{base_url}/", timeout=10)
        if r.status_code != 200:
            return False, f"API returned {r.status_code}: {r.text}"
        return True, "API reachable"
    except Exception as e:
        return False, f"API not reachable: {e}"


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


def clear_table(table_name: str):
    supabase = get_supabase()
    supabase.table(table_name).delete().neq("prediction_id", "").execute()


def clear_all_tables():
    supabase = get_supabase()
    supabase.table("smartport_predictions").delete().neq("prediction_id", "").execute()
    supabase.table("stockout_predictions").delete().neq("prediction_id", "").execute()
    supabase.table("nasa_predictions").delete().neq("prediction_id", "").execute()


render_page_header(
    "⬆️ Upload Center",
    "Run manual uploads, inspect module status, and manage stored prediction batches.",
    tags=["Manual Uploads", "Batch Control", "Supabase Persistence"]
)

ok, msg = api_healthcheck(API_BASE_URL)

with st.sidebar:
    st.subheader("Platform Configuration")
    st.write("**API Base URL**")
    st.code(API_BASE_URL)

    if ok:
        st.success(msg)
    else:
        st.error(msg)

    st.info(
        "The UI sends uploaded files to the FastAPI service. "
        "The API runs inference and stores results in Supabase."
    )

st.subheader("Platform Workflow")
st.markdown(
    """
<div class="suite-card">
<p><strong>Manual Uploads</strong><br>
You upload a file from this page. The API processes it, generates predictions, and stores them as a new batch.</p>

<p><strong>Automatic Demo Data</strong><br>
The suite also includes automation scripts that can periodically populate the database with demo predictions.</p>

<p><strong>Automatic Cleanup</strong><br>
Old prediction batches can be removed automatically to keep the database manageable.</p>

<p><strong>Batch Logic</strong><br>
Each upload creates a new <code>batch_id</code>, so manual uploads and automatic demo runs can coexist without overwriting one another.</p>
</div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Module Overview")

overview_cols = st.columns(3)
module_keys = list(MODULES.keys())

for i, module_name in enumerate(module_keys):
    module = MODULES[module_name]
    total_batches, total_predictions, last_run = fetch_table_metrics(module["table"])

    with overview_cols[i]:
        st.markdown(
            f"""
<div class="suite-card">
<h3>{module_name}</h3>
<p>{module["description"]}</p>
<p><strong>Demo file:</strong> <code>{module["demo_file"]}</code></p>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.metric("Stored Batches", total_batches)
        st.metric("Stored Predictions", total_predictions)
        st.caption(f"Last run: {last_run if last_run else 'N/A'}")

left_col, right_col = st.columns([1.4, 1])

with left_col:
    st.subheader("Manual Upload")

    module_name = st.selectbox("Choose a module", list(MODULES.keys()))
    module = MODULES[module_name]

    st.write(module["description"])
    st.caption(f"Accepted formats: {', '.join(module['accepted'])}")

    uploaded = st.file_uploader(
        label=module["help"],
        type=[ext.replace(".", "") for ext in module["accepted"]],
        key=f"upload_{module_name}",
    )

    run = st.button("🚀 Run Predictions", disabled=(uploaded is None), use_container_width=True)

    if run:
        try:
            url = f"{API_BASE_URL}{module['endpoint']}"

            if uploaded is None:
                st.warning("Please select a file before running predictions.")
            else:
                content_type = "text/plain" if uploaded.name.lower().endswith(".txt") else "text/csv"

                with st.spinner("Sending file to API and running inference..."):
                    files = {
                        "file": (
                            uploaded.name,
                            uploaded.getvalue(),
                            content_type,
                        )
                    }
                    r = requests.post(url, files=files, timeout=300)

                if r.status_code != 200:
                    st.error(f"API error {r.status_code}: {r.text}")
                else:
                    payload = r.json()

                    if payload.get("success") is True:
                        st.success("Predictions completed successfully.")
                    else:
                        st.warning("Request completed, but the engine reported an error.")

                    st.json(payload)

                    cols = st.columns(3)
                    with cols[0]:
                        st.metric("Processed Records", payload.get("processed_records", "—"))
                    with cols[1]:
                        st.metric("Batch ID", payload.get("batch_id", "—"))
                    with cols[2]:
                        dist = payload.get("distribution")
                        st.metric("Has Distribution", "Yes" if isinstance(dist, dict) else "No")

                    st.subheader("What happens next")
                    st.write(
                        "Open the corresponding dashboard page to inspect the latest stored batch. "
                        "Each run is stored separately using a unique `batch_id`."
                    )

        except requests.exceptions.Timeout:
            st.error("Timeout: the API took too long to respond. Try a smaller file or increase server resources.")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

with right_col:
    st.subheader("Batch Management")

    selected_cleanup_module = st.selectbox(
        "Select module to clean",
        list(MODULES.keys()),
        key="cleanup_module"
    )

    cleanup_table = MODULES[selected_cleanup_module]["table"]
    cleanup_batches, cleanup_predictions, cleanup_last_run = fetch_table_metrics(cleanup_table)

    st.metric("Module Batches", cleanup_batches)
    st.metric("Module Predictions", cleanup_predictions)
    st.caption(f"Last run: {cleanup_last_run if cleanup_last_run else 'N/A'}")

    if st.button("Delete All Batches for Selected Module", use_container_width=True):
        try:
            clear_table(cleanup_table)
            st.success(f"All batches deleted for {selected_cleanup_module}")
            st.rerun()
        except Exception as e:
            st.error(f"Module cleanup failed: {e}")

    if st.button("Delete All Batches in Entire Suite", use_container_width=True):
        try:
            clear_all_tables()
            st.success("All prediction tables cleared across the suite.")
            st.rerun()
        except Exception as e:
            st.error(f"Global cleanup failed: {e}")

st.subheader("Operational Notes")
st.markdown(
    """
- Manual uploads create new batches and do **not** overwrite previous runs.
- Automatic demo loading can coexist with manual uploads.
- Cleanup can remove either one module's stored history or the full suite history.
- If you want a completely clean demo, clear the relevant table before uploading a new file.
"""
)