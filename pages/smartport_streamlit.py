import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from db.supabase_client import get_supabase

st.set_page_config(
    page_title="SmartPort AI | Command Center",
    page_icon="⚓",
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

def fetch_smartport_predictions(limit: int = 500) -> pd.DataFrame:
    supabase = get_client()
    if supabase is None:
        return pd.DataFrame()

    try:
        response = (
            supabase.table("smartport_predictions")
            .select("prediction_id,vessel_index,risk_score,risk_level,timestamp")
            .limit(limit)
            .execute()
        )
        df = pd.DataFrame(response.data or [])
        if not df.empty:
            df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.sort_values("timestamp", ascending=False)
            df["recommended_action"] = df["risk_level"].map({
                "CRITICAL": "Immediate tugboat standby and route deviation review.",
                "WARNING": "Increase monitoring and validate AIS consistency.",
                "NORMAL": "Routine trajectory monitoring."
            }).fillna("Routine trajectory monitoring.")
        return df
    except Exception:
        return pd.DataFrame()

def send_telegram_message(message: str) -> tuple[bool, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            return True, "Telegram notification sent successfully."
        return False, f"Telegram API error: {response.status_code}"
    except Exception as e:
        return False, str(e)

df = fetch_smartport_predictions()

st.title("⚓ SmartPort AI | Command Center")
st.markdown("---")

if not df.empty:
    total_vessels = len(df)
    critical_alerts = int((df["risk_level"] == "CRITICAL").sum())
    avg_risk = float(df["risk_score"].fillna(0).mean())

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Active Vessel Records", total_vessels)
    with m2:
        st.metric("Critical Alerts", critical_alerts)
    with m3:
        st.metric("Average Risk Score", f"{avg_risk:.2f}")

    st.write("")

    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Live Vessel Risk Monitor")

        show_cols = [
            "prediction_id",
            "vessel_index",
            "risk_score",
            "risk_level",
            "recommended_action",
            "timestamp"
        ]
        st.dataframe(df[show_cols].head(50), width="stretch", hide_index=True)

        chart_df = df["risk_level"].value_counts().reset_index()
        chart_df.columns = ["risk_level", "count"]
        fig = px.bar(chart_df, x="risk_level", y="count", title="Risk Level Distribution")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, width="stretch")

    with right_col:
        st.subheader("🕹️ Tactical Control")

        vessel_options = df["vessel_index"].astype(str).unique().tolist()
        selected_vessel = st.selectbox("Select Target Vessel", vessel_options)

        vessel_info = df[df["vessel_index"].astype(str) == str(selected_vessel)].iloc[0]
        st.info(f"**AI Recommendation:**\n{vessel_info['recommended_action']}")

        dispatch_order = st.selectbox("Select Dispatch Order", [
            "Immediate Berth Reassignment",
            "Priority Inspection Hold",
            "AIS Protocol Synchronization",
            "Manual Port Clearance"
        ])

        if st.button("Execute & Notify Telegram"):
            message = (
                f"🚨 *SMARTPORT OPERATIONAL COMMAND*\n\n"
                f"🚢 *Vessel Index:* {selected_vessel}\n"
                f"⚠️ *Risk Level:* {vessel_info['risk_level']}\n"
                f"📈 *Risk Score:* {float(vessel_info['risk_score']):.3f}\n"
                f"⚙️ *Dispatch Order:* {dispatch_order}\n"
                f"📋 *AI Recommendation:* {vessel_info['recommended_action']}\n"
                f"✅ *Status:* Dispatch Confirmed"
            )
            ok, msg = send_telegram_message(message)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
else:
    st.warning("No SmartPort prediction data found in Supabase.")