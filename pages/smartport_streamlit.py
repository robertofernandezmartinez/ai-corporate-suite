import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from db.supabase_client import get_supabase

# =========================
# SmartPort Dashboard
# =========================
# This dashboard reads predictions from Supabase and ONLY shows the latest batch_id
# to avoid mixing results from different uploads.

st.set_page_config(page_title="SmartPort AI | Command Center", page_icon="⚓", layout="wide")


@st.cache_resource
def get_client():
    # Cached Supabase client across reruns
    return get_supabase()


def fetch_latest_batch_id() -> str | None:
    # Get the most recent batch by created_at
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
    return rows[0].get("batch_id")


def fetch_latest_batch_data(batch_id: str, limit: int = 5000) -> pd.DataFrame:
    # Fetch predictions for the given batch_id only
    supabase = get_client()
    resp = (
        supabase.table("smartport_predictions")
        .select("prediction_id,vessel_index,risk_score,risk_level,timestamp,batch_id,created_at")
        .eq("batch_id", batch_id)
        .limit(limit)
        .execute()
    )
    df = pd.DataFrame(resp.data or [])
    if not df.empty:
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
    return df


def send_telegram_message(message: str) -> tuple[bool, str]:
    # Optional: send alerts via Telegram if tokens are configured
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False, "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=20)
    if r.status_code == 200:
        return True, "Telegram message sent."
    return False, f"Telegram API error {r.status_code}: {r.text}"


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


def recommended_action(level: str) -> str:
    return {
        "CRITICAL": "IMMEDIATE: Tugboat standby & route deviation review.",
        "WARNING": "PROACTIVE: Increase monitoring and validate AIS stability.",
        "NORMAL": "ROUTINE: Vessel on standard trajectory.",
    }.get(level, "ROUTINE: Vessel on standard trajectory.")


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
        title="Risk Level Distribution (Latest Batch)",
    )
    st.plotly_chart(fig, width="stretch")

    show_cols = ["prediction_id", "vessel_index", "risk_score", "risk_level", "recommended_action", "timestamp"]
    st.dataframe(df[show_cols].head(50), width="stretch", hide_index=True)

with right:
    st.subheader("🕹️ Tactical Control")

    vessel_options = df["vessel_index"].astype(int).astype(str).unique().tolist()
    selected_vessel = st.selectbox("Select Target Vessel", vessel_options)

    row = df[df["vessel_index"].astype(int).astype(str) == str(selected_vessel)].iloc[0]

    st.info(f"**AI Recommendation:**\n{row['recommended_action']}")
    dispatch_order = st.selectbox(
        "Select Dispatch Order",
        [
            "Immediate Berth Reassignment",
            "Priority Inspection Hold",
            "AIS Protocol Synchronization",
            "Manual Port Clearance",
        ],
    )

    if st.button("Execute & Notify Telegram"):
        msg = (
            f"SMARTPORT COMMAND\n"
            f"Vessel Index: {selected_vessel}\n"
            f"Risk Level: {row['risk_level']}\n"
            f"Risk Score: {float(row['risk_score']):.3f}\n"
            f"Dispatch: {dispatch_order}\n"
            f"Recommendation: {row['recommended_action']}\n"
            f"Batch: {batch_id}"
        )
        ok, info = send_telegram_message(msg)
        st.success(info) if ok else st.error(info)

st.caption(f"Showing batch_id: {batch_id}")