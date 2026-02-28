import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from db.supabase_client import get_supabase

st.set_page_config(
    page_title="NASA Predictive Maintenance",
    page_icon="✈️",
    layout="wide"
)

st.markdown("""
<style>
    footer {visibility: hidden;}
    .status-box {
        padding: 0.9rem 1rem;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.25);
        background: rgba(127,127,127,0.06);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_nasa_predictions(limit: int = 5000) -> pd.DataFrame:
    supabase = get_client()
    if supabase is None:
        return pd.DataFrame()

    try:
        response = (
            supabase.table("nasa_predictions")
            .select("prediction_id,unit_id,predicted_rul,timestamp")
            .limit(limit)
            .execute()
        )
        df = pd.DataFrame(response.data or [])

        if not df.empty:
            df["predicted_rul"] = pd.to_numeric(df["predicted_rul"], errors="coerce")
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        return df
    except Exception:
        return pd.DataFrame()

def build_degradation_curve(engine_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a readable degradation curve.
    We do not have 'time_in_cycles' in Supabase, so we use observation order.
    This avoids the unreadable vertical timestamp chart.
    """
    curve_df = engine_df.copy().reset_index(drop=True)
    curve_df["observation_index"] = np.arange(1, len(curve_df) + 1)
    return curve_df

df_results = fetch_nasa_predictions()

st.title("✈️ Predictive Maintenance Dashboard")
st.markdown("---")

if df_results.empty:
    st.error("No NASA prediction records found in Supabase.")
    st.stop()

unit_ids = sorted(df_results["unit_id"].dropna().astype(str).unique().tolist())
selected_unit = st.sidebar.selectbox("Engine Unit ID", unit_ids)

engine_data = df_results[df_results["unit_id"].astype(str) == str(selected_unit)].copy()

# Keep insertion order if timestamps are almost identical
engine_data = engine_data.reset_index(drop=True)

if engine_data.empty:
    st.warning("No records found for the selected engine.")
    st.stop()

curve_df = build_degradation_curve(engine_data)

latest_rul = float(curve_df["predicted_rul"].iloc[-1])
total_points = len(curve_df)

status = "STABLE"
if latest_rul < 30:
    status = "CRITICAL"
elif latest_rul < 75:
    status = "MAINTENANCE REQUIRED"

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Total Observations", total_points)
with m2:
    st.metric("Remaining Useful Life", f"{latest_rul:.0f} cycles")
with m3:
    st.metric("Health Index", status)

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=curve_df["observation_index"],
        y=curve_df["predicted_rul"],
        mode="lines+markers",
        name="Predicted RUL",
        line=dict(color="#00B5F7", width=3)
    )
)

# Warning threshold
fig.add_hline(
    y=75,
    line_dash="dash",
    line_color="#F4C542",
    annotation_text="Warning threshold",
    annotation_position="top left"
)

# Critical threshold
fig.add_hline(
    y=30,
    line_dash="dash",
    line_color="#FF4B4B",
    annotation_text="Critical threshold",
    annotation_position="bottom right"
)

fig.update_layout(
    title="RUL Degradation Curve",
    xaxis_title="Observation Sequence",
    yaxis_title="Predicted RUL",
    height=500
)

st.plotly_chart(fig, width="stretch")

st.markdown("---")
st.subheader("Latest NASA Prediction Records")

show_df = curve_df[["prediction_id", "unit_id", "predicted_rul", "timestamp"]].copy()
st.dataframe(show_df.tail(25).iloc[::-1], width="stretch", hide_index=True)

if latest_rul < 30:
    st.error("Critical degradation level detected. Maintenance intervention should be prioritized immediately.")
elif latest_rul < 75:
    st.warning("The engine is approaching the maintenance warning zone. Plan intervention soon.")
else:
    st.success("The engine remains above the warning zone.")