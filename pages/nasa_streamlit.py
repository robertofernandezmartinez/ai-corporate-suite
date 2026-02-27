import streamlit as st
import pandas as pd
import joblib
import os
import plotly.graph_objects as go
import numpy as np

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="NASA Jet Engine RUL", page_icon="✈️", layout="wide")

# 2. ASSET LOADING (Fixed paths for 'pages' folder)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT_DIR, "04_Models", "nasa_model.pkl")
DATA_PATH = os.path.join(ROOT_DIR, "05_Results", "predictions_validation_FD001.csv")

@st.cache_resource
def load_assets():
    if not os.path.exists(MODEL_PATH) or not os.path.exists(DATA_PATH):
        return None, None
    try:
        m = joblib.load(MODEL_PATH)
        d = pd.read_csv(DATA_PATH)
        return m, d
    except Exception as e:
        st.error(f"Error loading assets: {e}")
        return None, None

model, df_results = load_assets()

if df_results is not None:
    # Sidebar selection
    unit_ids = df_results['unit_number'].unique()
    selected_unit = st.sidebar.selectbox("Engine Unit ID:", unit_ids)

    engine_data = df_results[df_results['unit_number'] == selected_unit].sort_values('time_in_cycles')
    current_cycle = int(engine_data['time_in_cycles'].max())
    predicted_rul = float(engine_data['predicted_RUL'].iloc[-1])

    # DASHBOARD DISPLAY
    st.title("✈️ Predictive Maintenance Dashboard")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Cycles", current_cycle)
    m2.metric("Remaining Useful Life", f"{predicted_rul:.0f} cycles")
    
    status = "STABLE"
    if predicted_rul < 30: status = "CRITICAL"
    elif predicted_rul < 75: status = "MAINTENANCE REQUIRED"
    m3.metric("Health Index", status)

    # Plotly Chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=engine_data['time_in_cycles'], y=engine_data['predicted_RUL'], name="RUL Trend"))
    fig.update_layout(title="RUL Degradation Curve", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Assets not found. Check if '04_Models' and '05_Results' folders exist in root.")