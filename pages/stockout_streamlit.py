import streamlit as st
import pandas as pd
import plotly.express as px

from db.supabase_client import get_supabase


st.set_page_config(
    page_title="Stockout AI | Retail Risk Monitor",
    page_icon="📦",
    layout="wide"
)


@st.cache_resource
def get_client():
    return get_supabase()


# -------------------------
# System Metrics
# -------------------------

def fetch_system_metrics():

    supabase = get_client()

    if not supabase:
        return 0, 0, None

    resp = supabase.table("stockout_predictions").select("batch_id,created_at").execute()

    rows = resp.data or []

    total_predictions = len(rows)

    unique_batches = len(set([r["batch_id"] for r in rows]))

    latest_run = None
    if rows:
        latest_run = max(r["created_at"] for r in rows)

    return unique_batches, total_predictions, latest_run


# -------------------------
# Latest Batch
# -------------------------

def fetch_latest_batch_id():

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


def fetch_latest_batch_data(batch_id):

    supabase = get_client()

    resp = (
        supabase.table("stockout_predictions")
        .select("prediction_id,product_id,risk_score,financial_impact,risk_level,batch_id")
        .eq("batch_id", batch_id)
        .execute()
    )

    df = pd.DataFrame(resp.data or [])

    if not df.empty:
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
        df["financial_impact"] = pd.to_numeric(df["financial_impact"], errors="coerce")

    return df


# =========================
# UI
# =========================

st.title("📦 Stockout AI | Retail Risk Monitor")

st.markdown("---")


# -------------------------
# System Metrics
# -------------------------

total_batches, total_predictions, last_run = fetch_system_metrics()

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Total Prediction Batches", total_batches)

with m2:
    st.metric("Total Predictions Stored", total_predictions)

with m3:
    st.metric("Last System Run", last_run if last_run else "N/A")

st.markdown("---")


batch_id = fetch_latest_batch_id()

if not batch_id:
    st.warning("No Stockout prediction batches found yet.")
    st.stop()

df = fetch_latest_batch_data(batch_id)

if df.empty:
    st.warning("Latest Stockout batch returned no rows.")
    st.stop()


# -------------------------
# KPIs
# -------------------------

total_products = df["product_id"].nunique()
high_risk = (df["risk_level"] == "HIGH").sum()
total_loss = df["financial_impact"].sum()

k1, k2, k3 = st.columns(3)

with k1:
    st.metric("Products Evaluated", total_products)

with k2:
    st.metric("High Risk Items", high_risk)

with k3:
    st.metric("Total Financial Impact", f"${total_loss:,.0f}")


# -------------------------
# Visualization
# -------------------------

fig = px.bar(
    df,
    x="product_id",
    y="financial_impact",
    color="risk_level",
    title="Predicted Financial Impact by Product",
)

st.plotly_chart(fig, width="stretch")


st.dataframe(
    df.head(100),
    width="stretch",
    hide_index=True
)


st.caption(f"Showing batch_id: {batch_id}")