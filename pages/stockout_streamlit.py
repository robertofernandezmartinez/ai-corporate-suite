import streamlit as st
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from db.supabase_client import get_supabase

st.set_page_config(
    page_title="Stockout AI Suite | Strategic Replenishment",
    page_icon="📦",
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
    div[data-testid="stMetricValue"] { color: #ffffff; }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "models" / "stockout_model.pkl"

@st.cache_resource
def load_model():
    if not MODEL_PATH.exists():
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_predictions(limit: int = 200) -> pd.DataFrame:
    supabase = get_client()
    if supabase is None:
        return pd.DataFrame()

    try:
        response = (
            supabase.table("stockout_predictions")
            .select("prediction_id,product_id,risk_score,risk_level,financial_impact,timestamp")
            .limit(limit)
            .execute()
        )
        df = pd.DataFrame(response.data or [])
        if not df.empty and "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.sort_values("timestamp", ascending=False)
        return df
    except Exception:
        return pd.DataFrame()

pipeline = load_model()
predictions_df = fetch_predictions()

st.sidebar.title("Simulation Panel")

with st.sidebar:
    st.subheader("📦 Inventory Inputs")
    inv_level = st.slider("Current Stock (Units)", 0, 5000, 450)
    units_sold = st.slider("Units Sold (Last 24h)", 0, 500, 30)

    st.subheader("💰 Pricing")
    price = st.number_input("Our Price ($)", min_value=0.0, value=150.0)
    comp_price = st.number_input("Competitor Price ($)", min_value=0.0, value=145.0)
    discount = st.slider("Discount (%)", 0.0, 0.5, 0.1)

    st.subheader("🌍 Context")
    region = st.selectbox("Region", ["North", "South", "East", "West", "Central"])
    category = st.selectbox("Category", ["Electronics", "Fashion", "Home", "Toys", "Groceries"])
    weather = st.selectbox("Weather Condition", ["Sunny", "Rainy", "Cloudy"])
    seasonality = st.selectbox("Seasonality", ["Spring", "Summer", "Autumn", "Winter"])
    holiday_promo = st.selectbox("Holiday / Promotion", ["0", "1"])
    is_weekend = st.checkbox("Is it a Weekend?")

st.title("📦 Strategic Stockout Early Warning System")
st.markdown("---")

input_df = pd.DataFrame({
    "store_id": ["S_DEMO"],
    "product_id": ["P_DEMO"],
    "category": [category],
    "region": [region],
    "weather": [weather],
    "holiday_promo": [holiday_promo],
    "seasonality": [seasonality],
    "month": ["2"],
    "day_of_week": ["6" if is_weekend else "3"],
    "inventory_level": [float(inv_level)],
    "units_sold": [float(units_sold)],
    "price": [float(price)],
    "discount": [float(discount)],
    "competitor_pricing": [float(comp_price)],
    "is_weekend": [1.0 if is_weekend else 0.0]
})

if pipeline is not None:
    try:
        prob = float(pipeline.predict_proba(input_df)[0][1])
    except Exception:
        prob = 0.15
        st.warning("The model is available, but the simulation input did not match the pipeline exactly. Showing fallback output.")
else:
    prob = 0.15
    st.warning("Model file not found in Railway. Showing dashboard with fallback simulation only.")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Risk Probability", f"{prob * 100:.1f}%")
with col2:
    if prob > 0.75:
        status = "🚨 CRITICAL"
    elif prob > 0.40:
        status = "⚠️ WARNING"
    else:
        status = "✅ SAFE"
    st.metric("Inventory Health", status)
with col3:
    financial_impact = prob * price * units_sold
    st.metric("Revenue at Risk", f"${financial_impact:,.2f}")

st.subheader("Safety Stock Analysis")
st.progress(float(np.clip(prob, 0.0, 1.0)))

st.markdown("---")
if prob > 0.75:
    st.error(f"Immediate action recommended for **{category}** in **{region}**.")
elif prob > 0.40:
    st.warning(f"Watchlist status: monitor **{category}** sales velocity and replenishment timing.")
else:
    st.success("Inventory appears healthy for the current scenario.")

st.markdown("---")
st.subheader("Recent Stockout Predictions")

if not predictions_df.empty:
    st.dataframe(predictions_df.head(25), width="stretch", hide_index=True)

    high_risk = int(predictions_df["risk_level"].isin(["HIGH", "CRITICAL"]).sum())
    total_exposure = float(pd.to_numeric(predictions_df["financial_impact"], errors="coerce").fillna(0).sum())

    k1, k2 = st.columns(2)
    with k1:
        st.metric("High / Critical Alerts", high_risk)
    with k2:
        st.metric("Total Financial Exposure", f"${total_exposure:,.2f}")
else:
    st.info("No stockout prediction records found in Supabase yet.")

st.caption("Retail Stockout AI Suite | Railway + Supabase Deployment")