import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.supabase_client import get_supabase

st.set_page_config(
    page_title="NASA Jet Engine RUL",
    page_icon="✈️",
    layout="wide"
)

st.markdown("""
<style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #3e4259;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_nasa_predictions(limit: int = 500) -> pd.DataFrame:
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
            df = df.sort_values("timestamp", ascending=False)
        return df
    except Exception:
        return pd.DataFrame()

df_results = fetch_nasa_predictions()

st.title("✈️ Predictive Maintenance Dashboard")
st.markdown("---")

if not df_results.empty:
    unit_ids = sorted(df_results["unit_id"].dropna().astype(str).unique().tolist())
    selected_unit = st.sidebar.selectbox("Engine Unit ID", unit_ids)

    engine_data = df_results[df_results["unit_id"].astype(str) == str(selected_unit)].copy()
    engine_data = engine_data.sort_values("timestamp")

    latest_row = engine_data.iloc[-1]
    latest_rul = float(latest_row["predicted_rul"])
    total_records = len(engine_data)

    status = "STABLE"
    if latest_rul < 30:
        status = "CRITICAL"
    elif latest_rul < 75:
        status = "MAINTENANCE REQUIRED"

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Records for Unit", total_records)
    with m2:
        st.metric("Remaining Useful Life", f"{latest_rul:.0f} cycles")
    with m3:
        st.metric("Health Index", status)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=engine_data["timestamp"],
            y=engine_data["predicted_rul"],
            mode="lines+markers",
            name="Predicted RUL"
        )
    )
    fig.update_layout(
        title="Predicted RUL Over Time",
        template="plotly_dark",
        xaxis_title="Timestamp",
        yaxis_title="Predicted RUL"
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("Latest NASA Prediction Records")
    st.dataframe(df_results.head(25), width="stretch", hide_index=True)
else:
    st.error("No NASA prediction records found in Supabase.")