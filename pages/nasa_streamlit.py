import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.supabase_client import get_supabase

st.set_page_config(
    page_title="NASA Predictive Maintenance",
    page_icon="✈️",
    layout="wide"
)

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_nasa_predictions(limit: int = 10000) -> pd.DataFrame:
    supabase = get_client()
    if supabase is None:
        return pd.DataFrame()

    response = (
        supabase.table("nasa_predictions")
        .select("prediction_id,unit_id,cycle,predicted_rul,timestamp")
        .limit(limit)
        .execute()
    )

    df = pd.DataFrame(response.data or [])
    if not df.empty:
        df["predicted_rul"] = pd.to_numeric(df["predicted_rul"], errors="coerce")
        df["cycle"] = pd.to_numeric(df["cycle"], errors="coerce")
        df = df.sort_values(["unit_id", "cycle"])
    return df

df_results = fetch_nasa_predictions()

st.title("✈️ Predictive Maintenance Dashboard")
st.markdown("---")

if df_results.empty:
    st.error("No NASA prediction records found.")
    st.stop()

unit_ids = sorted(df_results["unit_id"].astype(str).unique().tolist())
selected_unit = st.sidebar.selectbox("Engine Unit ID", unit_ids)

engine_data = df_results[df_results["unit_id"].astype(str) == str(selected_unit)]

if engine_data.empty:
    st.warning("No records for this engine.")
    st.stop()

engine_data = engine_data.sort_values("cycle")

latest_rul = float(engine_data["predicted_rul"].iloc[-1])
total_cycles = int(engine_data["cycle"].iloc[-1])

if latest_rul < 30:
    status = "CRITICAL"
elif latest_rul < 75:
    status = "MAINTENANCE REQUIRED"
else:
    status = "STABLE"

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Total Cycles", total_cycles)
with m2:
    st.metric("Remaining Useful Life", f"{latest_rul:.0f} cycles")
with m3:
    st.metric("Health Index", status)

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=engine_data["cycle"],
        y=engine_data["predicted_rul"],
        mode="lines+markers",
        name="Predicted RUL",
        line=dict(color="#00B5F7", width=3)
    )
)

fig.add_hline(
    y=75,
    line_dash="dash",
    line_color="#F4C542",
    annotation_text="Warning threshold"
)

fig.add_hline(
    y=30,
    line_dash="dash",
    line_color="#FF4B4B",
    annotation_text="Critical threshold"
)

fig.update_layout(
    title="RUL Degradation Curve",
    xaxis_title="Cycle",
    yaxis_title="Predicted RUL",
    height=500
)

st.plotly_chart(fig, width="stretch")

if latest_rul < 30:
    st.error("Critical degradation detected. Immediate maintenance required.")
elif latest_rul < 75:
    st.warning("Approaching maintenance threshold.")
else:
    st.success("Engine operating within safe limits.")