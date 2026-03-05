import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px

from db.supabase_client import get_supabase

st.set_page_config(page_title="SmartPort AI | Command Center", page_icon="⚓", layout="wide")


@st.cache_resource
def get_client():
    return get_supabase()


def fetch_latest_batch_id():
    supabase = get_client()
    if not supabase:
        return None

    resp = (
        supabase.table("smartport_predictions")
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
        supabase.table("smartport_predictions")
        .select("*")
        .eq("batch_id", batch_id)
        .limit(5000)
        .execute()
    )

    df = pd.DataFrame(resp.data or [])

    if not df.empty:
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")

    return df


st.title("⚓ SmartPort AI | Command Center")
st.markdown("---")

batch_id = fetch_latest_batch_id()

if not batch_id:
    st.warning("No SmartPort prediction batches found yet. Upload a dataset first.")
    st.stop()

df = fetch_latest_batch_data(batch_id)

if df.empty:
    st.warning("Latest SmartPort batch returned no rows.")
    st.stop()


def recommended_action(level):
    return {
        "CRITICAL": "IMMEDIATE: Tugboat standby & route deviation review.",
        "WARNING": "PROACTIVE: Increase monitoring and validate AIS stability.",
        "NORMAL": "ROUTINE: Vessel on standard trajectory.",
    }.get(level, "ROUTINE")


df["recommended_action"] = df["risk_level"].map(recommended_action)

total = len(df)
critical = int((df["risk_level"] == "CRITICAL").sum())
avg_risk = float(df["risk_score"].fillna(0).mean())

m1, m2, m3 = st.columns(3)

with m1:
    st.metric("Active Vessel Records", total)

with m2:
    st.metric("Critical Alerts", critical)

with m3:
    st.metric("Average Risk Score", f"{avg_risk:.2f}")


left, right = st.columns([2, 1])

with left:

    st.subheader("Live Vessel Risk Monitor")

    dist = df["risk_level"].value_counts().reset_index()
    dist.columns = ["risk_level", "count"]

    fig = px.bar(
        dist,
        x="risk_level",
        y="count",
        color="risk_level",
        title="Risk Level Distribution"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df.head(50), use_container_width=True)

with right:

    st.subheader("🕹️ Tactical Control")

    vessel_options = df["vessel_index"].astype(str).unique()

    vessel = st.selectbox("Select Vessel", vessel_options)

    row = df[df["vessel_index"].astype(str) == vessel].iloc[0]

    st.info(row["recommended_action"])

st.caption(f"Batch: {batch_id}")