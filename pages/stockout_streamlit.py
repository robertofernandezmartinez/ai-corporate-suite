import streamlit as st
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from db.supabase_client import get_supabase

st.set_page_config(page_title="Stockout AI | Dashboard", page_icon="📦", layout="wide")

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "models" / "stockout_model.pkl"

@st.cache_resource
def load_model():
    try:
        return joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None
    except Exception:
        return None

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_latest_batch_id() -> str | None:
    supabase = get_client()
    if not supabase:
        return None
    resp = (
        supabase.table("stockout_predictions")
        .select("batch_id,created_at")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    return rows[0].get("batch_id")

def fetch_latest_batch_data(batch_id: str, limit: int = 5000) -> pd.DataFrame:
    supabase = get_client()
    resp = (
        supabase.table("stockout_predictions")
        .select("prediction_id,product_id,risk_score,risk_level,financial_impact,timestamp,batch_id,created_at")
        .eq("batch_id", batch_id)
        .limit(limit)
        .execute()
    )
    df = pd.DataFrame(resp.data or [])
    if not df.empty:
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
        df["financial_impact"] = pd.to_numeric(df["financial_impact"], errors="coerce").fillna(0)
    return df

pipeline = load_model()

st.title("📦 Stockout Risk Dashboard")
st.markdown("---")

batch_id = fetch_latest_batch_id()
if not batch_id:
    st.warning("No Stockout prediction batches found yet. Upload a dataset first.")
    st.stop()

df = fetch_latest_batch_data(batch_id)
if df.empty:
    st.warning("Latest Stockout batch returned no rows.")
    st.stop()

total = len(df)
high = int(df["risk_level"].isin(["HIGH", "CRITICAL"]).sum())
exposure = float(df["financial_impact"].sum())

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Records (Latest Batch)", total)
with m2:
    st.metric("High/Critical Alerts", high)
with m3:
    st.metric("Total Exposure", f"${exposure:,.2f}")

st.subheader("Recent Predictions (Latest Batch)")
st.dataframe(df.head(50), width="stretch", hide_index=True)

st.caption(f"Showing batch_id: {batch_id}")