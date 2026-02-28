import streamlit as st
import pandas as pd
from db.supabase_client import get_supabase

st.set_page_config(
    page_title="AI Corporate Suite 2026",
    page_icon="🚀",
    layout="wide"
)

st.markdown("""
<style>
    .main { background-color: #0b1020; color: white; }
    div[data-testid="stMetric"] {
        background-color: #141a2e;
        border: 1px solid #2a3353;
        border-radius: 14px;
        padding: 16px;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_table(table_name: str, columns: str = "*", limit: int | None = None) -> pd.DataFrame:
    supabase = get_client()
    if supabase is None:
        return pd.DataFrame()

    try:
        query = supabase.table(table_name).select(columns)
        if limit is not None:
            query = query.limit(limit)
        response = query.execute()
        return pd.DataFrame(response.data or [])
    except Exception:
        return pd.DataFrame()

def safe_count(df: pd.DataFrame) -> int:
    return 0 if df.empty else len(df)

st.title("🚀 AI Corporate Suite 2026")
st.subheader("Main Control Center")

smartport_df = fetch_table(
    "smartport_predictions",
    "prediction_id,vessel_index,risk_score,risk_level,timestamp",
    limit=200
)

nasa_df = fetch_table(
    "nasa_predictions",
    "prediction_id,unit_id,predicted_rul,timestamp",
    limit=200
)

stockout_df = fetch_table(
    "stockout_predictions",
    "prediction_id,product_id,risk_score,risk_level,financial_impact,timestamp",
    limit=200
)

smartport_critical = 0 if smartport_df.empty else int((smartport_df["risk_level"] == "CRITICAL").sum())
nasa_critical = 0 if nasa_df.empty else int((pd.to_numeric(nasa_df["predicted_rul"], errors="coerce") < 30).sum())
stockout_high = 0 if stockout_df.empty else int(stockout_df["risk_level"].isin(["HIGH", "CRITICAL"]).sum())

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("🚢 SmartPort Alerts", smartport_critical)
with c2:
    st.metric("🔧 NASA Engines at Risk", nasa_critical)
with c3:
    stockout_status = "LOW" if stockout_high == 0 else ("MEDIUM" if stockout_high < 10 else "HIGH")
    st.metric("📦 Stockout Level", stockout_status)

st.markdown("---")
st.subheader("Recent System Activity")

recent_frames = []

if not smartport_df.empty:
    tmp = smartport_df.copy()
    tmp["module"] = "SmartPort"
    recent_frames.append(tmp)

if not nasa_df.empty:
    tmp = nasa_df.copy()
    tmp["module"] = "NASA"
    recent_frames.append(tmp)

if not stockout_df.empty:
    tmp = stockout_df.copy()
    tmp["module"] = "Stockout"
    recent_frames.append(tmp)

if recent_frames:
    recent_df = pd.concat(recent_frames, ignore_index=True)
    if "timestamp" in recent_df.columns:
        recent_df["timestamp"] = pd.to_datetime(recent_df["timestamp"], errors="coerce")
        recent_df = recent_df.sort_values("timestamp", ascending=False)
    st.dataframe(recent_df.head(20), width="stretch", hide_index=True)
else:
    st.info("No prediction data found yet in Supabase.")

st.markdown("---")
st.info("Tip: Use the left sidebar to open the SmartPort, NASA, and Stockout pages.")