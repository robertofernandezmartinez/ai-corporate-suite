import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.supabase_client import get_supabase

st.set_page_config(page_title="NASA Predictive Maintenance", page_icon="✈️", layout="wide")

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_latest_batch_id() -> str | None:
    supabase = get_client()
    if not supabase:
        return None
    resp = (
        supabase.table("nasa_predictions")
        .select("batch_id,created_at")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    return rows[0].get("batch_id")

def fetch_latest_batch_data(batch_id: str, limit: int = 20000) -> pd.DataFrame:
    supabase = get_client()
    resp = (
        supabase.table("nasa_predictions")
        .select("prediction_id,unit_id,cycle,predicted_rul,timestamp,batch_id,created_at")
        .eq("batch_id", batch_id)
        .limit(limit)
        .execute()
    )
    df = pd.DataFrame(resp.data or [])
    if not df.empty:
        df["unit_id"] = pd.to_numeric(df["unit_id"], errors="coerce")
        df["cycle"] = pd.to_numeric(df["cycle"], errors="coerce")
        df["predicted_rul"] = pd.to_numeric(df["predicted_rul"], errors="coerce")
        df = df.sort_values(["unit_id", "cycle"])
    return df

st.title("✈️ Predictive Maintenance Dashboard")
st.markdown("---")

batch_id = fetch_latest_batch_id()
if not batch_id:
    st.error("No NASA prediction batches found yet. Upload a dataset first.")
    st.stop()

df = fetch_latest_batch_data(batch_id)
if df.empty:
    st.error("Latest NASA batch exists but returned no rows.")
    st.stop()

unit_ids = sorted(df["unit_id"].dropna().astype(int).astype(str).unique().tolist())
selected_unit = st.sidebar.selectbox("Engine Unit ID", unit_ids)

engine_df = df[df["unit_id"].astype(int).astype(str) == str(selected_unit)].copy()
engine_df = engine_df.sort_values("cycle")

latest_rul = float(engine_df["predicted_rul"].iloc[-1])
total_cycles = int(engine_df["cycle"].iloc[-1])

status = "STABLE"
if latest_rul < 30:
    status = "CRITICAL"
elif latest_rul < 75:
    status = "MAINTENANCE REQUIRED"

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Total Cycles", total_cycles)
with m2:
    st.metric("Remaining Useful Life", f"{latest_rul:.0f} cycles")
with m3:
    st.metric("Health Index", status)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=engine_df["cycle"],
    y=engine_df["predicted_rul"],
    mode="lines+markers",
    name="Predicted RUL"
))
fig.add_hline(y=75, line_dash="dash", annotation_text="Warning threshold")
fig.add_hline(y=30, line_dash="dash", annotation_text="Critical threshold")
fig.update_layout(
    title="RUL Degradation Curve (Latest Batch)",
    xaxis_title="Cycle",
    yaxis_title="Predicted RUL",
    height=520
)
st.plotly_chart(fig, width="stretch")

st.markdown("---")
st.subheader("Latest Records (this batch)")
st.dataframe(engine_df.tail(25).iloc[::-1], width="stretch", hide_index=True)

st.caption(f"Showing batch_id: {batch_id}")