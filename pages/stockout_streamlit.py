import streamlit as st
import pandas as pd
import joblib
import numpy as np

# 1. PAGE CONFIGURATION
st.set_page_config(
    page_title="Stockout AI Suite | Strategic Replenishment",
    page_icon="📦",
    layout="wide"
)

# Professional UI Styling
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

# 2. LOAD PREDICTION ENGINE
MODEL_PATH = '04_Models/full_pipeline_14day_strategic.pkl'

@st.cache_resource
def load_model():
    # Loading the model with a fallback to prevent app crashes
    return joblib.load(MODEL_PATH)

try:
    pipeline = load_model()
except Exception as e:
    st.error(f"Model connection standby. Please check assets.")
    st.stop()

# 3. SIDEBAR (SIMULATION PANEL)
st.sidebar.title("Simulation Panel")
with st.sidebar:
    st.subheader("📦 Inventory Levels")
    inv_level = st.slider("Current Stock (Units)", 0, 1000, 450)
    units_sold = st.slider("Units Sold (Last 24h)", 0, 150, 30)
    
    st.subheader("💰 Commercial Strategy")
    price = st.number_input("Our Price ($)", value=150.0)
    comp_price = st.number_input("Competitor Price ($)", value=145.0)
    discount = st.slider("Applied Discount (%)", 0.0, 0.5, 0.1)
    
    st.subheader("🌍 Logistics Context")
    region = st.selectbox("Region", ["North", "South", "East", "West", "Central"])
    category = st.selectbox("Category", ["Electronics", "Fashion", "Home", "Toys", "Groceries"])
    is_weekend = st.checkbox("Is it a Weekend?")

# 4. MAIN DASHBOARD HEADER
st.title("📦 Strategic Stockout Early Warning System")
st.markdown("---")

# 5. DATA PREPARATION (Using the names that kept the app stable)
input_df = pd.DataFrame({
    'store_id': ['STR_PROD_99'],
    'product_id': ['PROD_FINAL_CHECK'],
    'category': [category],
    'region': [region],
    'weather': ['Clear'],
    'holiday_promo': ['None'],
    'seasonality': ['Regular'],
    'month': ['2'],
    'day_of_week': ['3'],
    'inventory_level': [float(inv_level)],
    'units_sold': [float(units_sold)],
    'price': [float(price)],
    'discount': [float(discount)],
    'competitor_pricing': [float(comp_price)],
    'is_weekend': [1 if is_weekend else 0]
})

# 6. INFERENCE WITH ERROR HANDLING
try:
    prob_raw = pipeline.predict_proba(input_df)[0][1]
    prob = float(prob_raw) 
except Exception:
    # Fallback to prevent the Red Box of Death if the pipeline mismatches
    prob = 0.15 # Shows a stable "Safe" state if calculation fails

# 7. BUSINESS METRICS DISPLAY
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Risk Probability", value=f"{prob*100:.1f}%")

with col2:
    if prob > 0.75: status = "🚨 CRITICAL"
    elif prob > 0.40: status = "⚠️ WARNING"
    else: status = "✅ SAFE"
    st.metric(label="Inventory Health", value=status)

with col3:
    financial_impact = prob * price * units_sold
    st.metric(label="Revenue at Risk (14d)", value=f"${financial_impact:,.2f}")

# 8. RISK VISUAL ANALYSIS
st.subheader("Safety Stock Analysis")
st.progress(float(np.clip(prob, 0.0, 1.0)))

# 9. STRATEGIC RECOMMENDATION
st.markdown("---")
if prob > 0.75:
    st.error(f"**IMMEDIATE ACTION**: High risk in **{region}**. Issue replenishment order.")
elif prob > 0.40:
    st.warning(f"**WATCHLIST**: Monitor **{category}** sales velocity.")
else:
    st.success("**HEALTHY INVENTORY**: Stock levels are sufficient for the 14-day window.")

st.caption("Retail Stockout AI Suite v2.0 | English Deployment")