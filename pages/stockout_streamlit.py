import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import joblib
from pathlib import Path
from sklearn.base import BaseEstimator, TransformerMixin
import __main__

from db.supabase_client import get_supabase


# ============================================================
# Required class for joblib unpickling
# ============================================================
class StockoutFeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.cat_cols = [
            "store_id",
            "category",
            "region",
            "weather",
            "holiday_promo",
            "seasonality",
            "month",
            "day_of_week",
            "product_id",
        ]
        self.num_cols = [
            "inventory_level",
            "units_sold",
            "price",
            "discount",
            "competitor_pricing",
            "is_weekend",
        ]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()

        mapping = {
            "Date": "date",
            "Store ID": "store_id",
            "Product ID": "product_id",
            "Category": "category",
            "Region": "region",
            "Inventory Level": "inventory_level",
            "Units Sold": "units_sold",
            "Units Ordered": "units_ordered",
            "Price": "price",
            "Discount": "discount",
            "Weather Condition": "weather",
            "Holiday/Promotion": "holiday_promo",
            "Competitor Pricing": "competitor_pricing",
            "Seasonality": "seasonality",
        }

        df = df.rename(columns=mapping)

        if "date" in df.columns:
            date_dt = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
            df["month"] = date_dt.dt.month.astype(str)
            df["day_of_week"] = date_dt.dt.dayofweek.astype(str)
            df["is_weekend"] = date_dt.dt.dayofweek.isin([5, 6]).astype(float)

        for col in self.cat_cols:
            if col not in df.columns:
                df[col] = "Unknown"
            df[col] = df[col].astype(str)

        for col in self.num_cols:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df[self.cat_cols + self.num_cols]


__main__.StockoutFeatureEngineer = StockoutFeatureEngineer


# ============================================================
# Page config
# ============================================================
st.set_page_config(
    page_title="Stockout AI | Retail Risk Monitor",
    page_icon="📦",
    layout="wide"
)

st.markdown(
    """
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
    """,
    unsafe_allow_html=True
)


# ============================================================
# Resources
# ============================================================
@st.cache_resource
def get_client():
    return get_supabase()


@st.cache_resource
def load_model():
    root_dir = Path(__file__).resolve().parents[1]
    model_path = root_dir / "models" / "stockout_model.pkl"
    return joblib.load(model_path)


# ============================================================
# Supabase helpers
# ============================================================
def fetch_system_metrics():
    try:
        supabase = get_client()
        resp = supabase.table("stockout_predictions").select("batch_id,created_at").execute()
        rows = resp.data or []

        total_predictions = len(rows)
        total_batches = len(set(r["batch_id"] for r in rows)) if rows else 0
        last_run = max(r["created_at"] for r in rows) if rows else None

        return total_batches, total_predictions, last_run
    except Exception:
        return 0, 0, None


def fetch_latest_batch_id():
    try:
        supabase = get_client()
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
        return rows[0]["batch_id"]
    except Exception:
        return None


def fetch_batch_data(batch_id: str) -> pd.DataFrame:
    try:
        supabase = get_client()
        resp = (
            supabase.table("stockout_predictions")
            .select("prediction_id,product_id,risk_score,financial_impact,risk_level,batch_id,created_at")
            .eq("batch_id", batch_id)
            .execute()
        )

        df = pd.DataFrame(resp.data or [])
        if not df.empty:
            df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
            df["financial_impact"] = pd.to_numeric(df["financial_impact"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def fetch_recent_batches(limit: int = 20):
    try:
        supabase = get_client()
        resp = (
            supabase.table("stockout_predictions")
            .select("batch_id,created_at")
            .order("created_at", desc=True)
            .limit(limit * 500)
            .execute()
        )

        df = pd.DataFrame(resp.data or [])
        if df.empty:
            return []

        df = df.drop_duplicates(subset=["batch_id"]).sort_values("created_at", ascending=False)
        return df["batch_id"].head(limit).tolist()
    except Exception:
        return []


# ============================================================
# Simulation helper
# ============================================================
def calculate_risk_level(prob: float) -> str:
    if prob >= 0.80:
        return "🚨 CRITICAL"
    if prob >= 0.50:
        return "⚠️ HIGH"
    if prob >= 0.20:
        return "🟡 MEDIUM"
    return "✅ LOW"


def build_simulation_df(
    category: str,
    region: str,
    weather: str,
    holiday_promo: str,
    seasonality: str,
    month: str,
    day_of_week: str,
    inventory_level: float,
    units_sold: float,
    price: float,
    discount: float,
    competitor_pricing: float,
    is_weekend: bool,
):
    return pd.DataFrame({
        "store_id": ["STR_PROD_99"],
        "product_id": ["PROD_FINAL_CHECK"],
        "category": [category],
        "region": [region],
        "weather": [weather],
        "holiday_promo": [holiday_promo],
        "seasonality": [seasonality],
        "month": [month],
        "day_of_week": [day_of_week],
        "inventory_level": [float(inventory_level)],
        "units_sold": [float(units_sold)],
        "price": [float(price)],
        "discount": [float(discount)],
        "competitor_pricing": [float(competitor_pricing)],
        "is_weekend": [1 if is_weekend else 0],
    })


# ============================================================
# Sidebar simulation panel
# ============================================================
st.sidebar.title("Simulation Panel")

with st.sidebar:
    st.subheader("📦 Inventory Levels")
    inventory_level = st.slider("Current Stock (Units)", 0, 1000, 450)
    units_sold = st.slider("Units Sold (Last 24h)", 0, 150, 30)

    st.subheader("💰 Commercial Strategy")
    price = st.number_input("Our Price ($)", min_value=0.0, value=150.0, step=1.0)
    competitor_pricing = st.number_input("Competitor Price ($)", min_value=0.0, value=145.0, step=1.0)
    discount = st.slider("Applied Discount (%)", 0.0, 0.5, 0.1)

    st.subheader("🌍 Logistics Context")
    region = st.selectbox("Region", ["North", "South", "East", "West", "Central"])
    category = st.selectbox("Category", ["Electronics", "Fashion", "Home", "Toys", "Groceries"])
    weather = st.selectbox("Weather", ["Clear", "Rainy", "Snowy", "Cloudy", "Storm"])
    holiday_promo = st.selectbox("Holiday / Promotion", ["None", "Holiday", "Promotion"])
    seasonality = st.selectbox("Seasonality", ["Regular", "Low", "High", "Peak"])
    month = st.selectbox("Month", [str(i) for i in range(1, 13)], index=1)
    day_of_week = st.selectbox("Day of Week", [str(i) for i in range(7)], index=3)
    is_weekend = st.checkbox("Is it a Weekend?")

    run_simulation = st.button("Run Simulation", use_container_width=True)


# ============================================================
# Main header
# ============================================================
st.title("📦 Strategic Stockout Early Warning System")
st.markdown("---")


# ============================================================
# Top system metrics
# ============================================================
total_batches, total_predictions, last_run = fetch_system_metrics()

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Total Prediction Batches", total_batches)

with m2:
    st.metric("Total Predictions Stored", total_predictions)

with m3:
    st.metric("Last System Run", last_run if last_run else "N/A")

st.markdown("---")


# ============================================================
# Simulation block
# ============================================================
st.subheader("Live Simulation")

try:
    pipeline = load_model()
    model_ready = True
except Exception:
    pipeline = None
    model_ready = False
    st.warning("Simulation model is not available right now.")

input_df = build_simulation_df(
    category=category,
    region=region,
    weather=weather,
    holiday_promo=holiday_promo,
    seasonality=seasonality,
    month=month,
    day_of_week=day_of_week,
    inventory_level=inventory_level,
    units_sold=units_sold,
    price=price,
    discount=discount,
    competitor_pricing=competitor_pricing,
    is_weekend=is_weekend,
)

if run_simulation or model_ready:
    try:
        if model_ready:
            prob_raw = pipeline.predict_proba(input_df)[0][1]
            prob = float(prob_raw)
        else:
            prob = 0.15
    except Exception:
        prob = 0.15

    status = calculate_risk_level(prob)
    financial_impact = prob * price * units_sold

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Risk Probability", f"{prob * 100:.1f}%")

    with c2:
        st.metric("Inventory Health", status)

    with c3:
        st.metric("Revenue at Risk (14d)", f"${financial_impact:,.2f}")

    st.subheader("Safety Stock Analysis")
    st.progress(float(np.clip(prob, 0.0, 1.0)))

    st.markdown("---")

    if prob > 0.75:
        st.error(f"**IMMEDIATE ACTION**: High risk in **{region}**. Issue replenishment order.")
    elif prob > 0.40:
        st.warning(f"**WATCHLIST**: Monitor **{category}** sales velocity.")
    else:
        st.success("**HEALTHY INVENTORY**: Stock levels are sufficient for the 14-day window.")

    with st.expander("View Simulation Input"):
        st.dataframe(input_df, use_container_width=True, hide_index=True)

st.markdown("---")


# ============================================================
# Historical analytics
# ============================================================
st.subheader("Stored Batch Analytics")

available_batches = fetch_recent_batches(limit=20)
latest_batch = fetch_latest_batch_id()

if not available_batches and latest_batch:
    available_batches = [latest_batch]

selected_batch = None
if available_batches:
    default_index = 0
    if latest_batch in available_batches:
        default_index = available_batches.index(latest_batch)

    selected_batch = st.selectbox(
        "Select Batch",
        available_batches,
        index=default_index
    )

if not selected_batch:
    st.info("No Stockout prediction batches found yet.")
    st.stop()

df = fetch_batch_data(selected_batch)

if df.empty:
    st.info("Selected batch returned no rows.")
    st.stop()

total_products = df["product_id"].nunique() if "product_id" in df.columns else 0
high_risk = int((df["risk_level"] == "HIGH").sum()) if "risk_level" in df.columns else 0
critical_risk = int((df["risk_level"] == "CRITICAL").sum()) if "risk_level" in df.columns else 0
total_loss = float(df["financial_impact"].sum()) if "financial_impact" in df.columns else 0.0

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric("Products Evaluated", total_products)

with k2:
    st.metric("High Risk Items", high_risk)

with k3:
    st.metric("Critical Risk Items", critical_risk)

with k4:
    st.metric("Total Financial Impact", f"${total_loss:,.0f}")

chart_col, table_col = st.columns([1.4, 1])

with chart_col:
    fig = px.bar(
        df.sort_values("financial_impact", ascending=False).head(30),
        x="product_id",
        y="financial_impact",
        color="risk_level",
        title="Predicted Financial Impact by Product"
    )
    st.plotly_chart(fig, use_container_width=True)

with table_col:
    if "risk_level" in df.columns:
        risk_dist = df["risk_level"].value_counts().reset_index()
        risk_dist.columns = ["risk_level", "count"]
        fig2 = px.pie(
            risk_dist,
            names="risk_level",
            values="count",
            title="Risk Distribution"
        )
        st.plotly_chart(fig2, use_container_width=True)

st.subheader("Batch Records")
st.dataframe(
    df.head(100),
    use_container_width=True,
    hide_index=True
)

st.caption(f"Showing batch_id: {selected_batch}")
st.caption("Retail Stockout AI Suite | Corporate Dashboard")