import os
import requests
import streamlit as st

# =========================
# Upload Center (Streamlit)
# =========================
# This page uploads raw datasets to the FastAPI backend. The backend runs inference and writes predictions to Supabase.
# IMPORTANT: In production, API_BASE_URL must be set to Railway FastAPI domain (e.g. https://api-xxx.up.railway.app)

st.set_page_config(
    page_title="Upload Center | AI Corporate Suite",
    page_icon="⬆️",
    layout="wide",
)

st.title("⬆️ Upload Center")
st.caption("Upload raw datasets to trigger predictions via the FastAPI backend and persist results into Supabase.")

# Base URL for FastAPI (Railway domain in production)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

MODULES = {
    "SmartPort (Maritime Risk)": {
        "endpoint": "/smartport/upload",
        "help": "Upload vessel tracking CSV (AIS-like telemetry).",
        "accepted": [".csv"],
    },
    "Stockout (Retail Risk)": {
        "endpoint": "/stockout/upload",
        "help": "Upload retail inventory CSV (PRO schema).",
        "accepted": [".csv"],
    },
    "NASA (RUL Prediction)": {
        "endpoint": "/nasa/upload",
        "help": "Upload NASA engine dataset CSV (must include unit_id, cycle).",
        "accepted": [".csv", ".txt"],
    },
}


def api_healthcheck(base_url: str) -> tuple[bool, str]:
    """
    Calls GET / on the FastAPI service to confirm the UI can reach the API.
    """
    try:
        r = requests.get(f"{base_url}/", timeout=10)
        if r.status_code != 200:
            return False, f"API returned {r.status_code}: {r.text}"
        return True, "API reachable (GET / returned 200)."
    except Exception as e:
        return False, f"API not reachable: {e}"


with st.sidebar:
    st.subheader("Configuration")
    st.write("**API Base URL**")
    st.code(API_BASE_URL)

    ok, msg = api_healthcheck(API_BASE_URL)
    st.success(msg) if ok else st.error(msg)

    st.info(
        "Set `API_BASE_URL` in Railway (UI service → Variables) to point Streamlit to your FastAPI service."
    )


module_name = st.selectbox("Choose a module", list(MODULES.keys()))
module = MODULES[module_name]

st.markdown("---")

st.subheader("1) Select a Raw Data File")
uploaded = st.file_uploader(
    label=module["help"],
    type=[ext.replace(".", "") for ext in module["accepted"]],
)

st.subheader("2) Run Predictions")
run = st.button("🚀 Run Predictions", disabled=(uploaded is None))

if run:
    try:
        url = f"{API_BASE_URL}{module['endpoint']}"

        with st.spinner("Sending file to API and running inference..."):
            # Provide filename + content + content-type
            files = {
                "file": (
                    uploaded.name,
                    uploaded.getvalue(),
                    "text/csv",
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

            # Quick highlights if available
            cols = st.columns(3)
            with cols[0]:
                st.metric("Processed Records", payload.get("processed_records", "—"))
            with cols[1]:
                st.metric("Batch ID", payload.get("batch_id", "—"))
            with cols[2]:
                dist = payload.get("distribution")
                st.metric("Has Distribution", "Yes" if isinstance(dist, dict) else "No")

            st.markdown("---")
            st.subheader("Next")
            st.write("Open the relevant dashboard page to view the **latest batch** (batch_id is used to avoid mixing data).")

    except requests.exceptions.Timeout:
        st.error("Timeout: the API took too long to respond. Try a smaller file or increase server resources.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")