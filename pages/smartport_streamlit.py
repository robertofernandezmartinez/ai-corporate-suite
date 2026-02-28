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
    footer {visibility: hidden;}

    .alert-chip-red {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        background: rgba(255, 75, 75, 0.15);
        color: #ff4b4b;
        font-weight: 600;
        border: 1px solid rgba(255, 75, 75, 0.35);
    }

    .alert-chip-yellow {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        background: rgba(244, 197, 66, 0.15);
        color: #d4a500;
        font-weight: 600;
        border: 1px solid rgba(244, 197, 66, 0.35);
    }

    .alert-chip-green {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        background: rgba(0, 200, 83, 0.12);
        color: #12b76a;
        font-weight: 600;
        border: 1px solid rgba(18, 183, 106, 0.35);
    }

    .panel-box {
        padding: 1rem;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,0.25);
        background: rgba(127,127,127,0.06);
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_client():
    return get_supabase()

def fetch_smartport_predictions(limit: int = 1000) -> pd.DataFrame:
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
    """
    Uses the same environment variable names as the working Telegram bot.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return False, "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in Railway variables."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=20)

        if response.status_code == 200:
            return True, "Telegram notification sent successfully."

        # Surface the actual Telegram API response for debugging
        return False, f"Telegram API error {response.status_code}: {response.text}"

    except Exception as e:
        return False, f"Telegram connection error: {e}"

df = fetch_smartport_predictions()

st.title("⚓ SmartPort AI | Command Center")
st.markdown("---")

if df.empty:
    st.warning("No SmartPort prediction data found in Supabase.")
    st.stop()

total_vessels = len(df)
critical_alerts = int((df["risk_level"] == "CRITICAL").sum())
warning_alerts = int((df["risk_level"] == "WARNING").sum())
avg_risk = float(df["risk_score"].fillna(0).mean())

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Active Vessel Records", total_vessels)
with m2:
    st.metric("Critical Alerts", critical_alerts)
with m3:
    st.metric("Average Risk Score", f"{avg_risk:.2f}")

st.write("")

c_status, c_actions = st.columns([2, 1])

with c_status:
    st.subheader("Live Vessel Risk Monitor")

    level_counts = df["risk_level"].value_counts().reset_index()
    level_counts.columns = ["risk_level", "count"]

    fig = px.bar(
        level_counts,
        x="risk_level",
        y="count",
        color="risk_level",
        color_discrete_map={
            "CRITICAL": "#FF4B4B",
            "WARNING": "#F4C542",
            "NORMAL": "#12B76A"
        },
        title="Risk Level Distribution"
    )
    st.plotly_chart(fig, width="stretch")

    show_cols = [
        "prediction_id",
        "vessel_index",
        "risk_score",
        "risk_level",
        "recommended_action",
        "timestamp"
    ]
    st.dataframe(df[show_cols].head(50), width="stretch", hide_index=True)

with c_actions:
    st.subheader("🕹️ Tactical Control")

    vessel_options = df["vessel_index"].astype(str).unique().tolist()
    selected_vessel = st.selectbox("Select Target Vessel", vessel_options)

    vessel_info = df[df["vessel_index"].astype(str) == str(selected_vessel)].iloc[0]

    level = str(vessel_info["risk_level"]).upper()
    if level == "CRITICAL":
        st.markdown('<div class="alert-chip-red">CRITICAL ALERT</div>', unsafe_allow_html=True)
    elif level == "WARNING":
        st.markdown('<div class="alert-chip-yellow">WARNING ALERT</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-chip-green">NORMAL STATUS</div>', unsafe_allow_html=True)

    st.write("")
    st.info(f"**AI Recommendation:**\n{vessel_info['recommended_action']}")

    dispatch_order = st.selectbox(
        "Select Dispatch Order",
        [
            "Immediate Berth Reassignment",
            "Priority Inspection Hold",
            "AIS Protocol Synchronization",
            "Manual Port Clearance"
        ]
    )

    if st.button("Execute & Notify Telegram"):
        telegram_msg = (
            f"🚨 *SMARTPORT OPERATIONAL COMMAND*\n\n"
            f"🚢 *Vessel Index:* {selected_vessel}\n"
            f"⚠️ *Risk Level:* {vessel_info['risk_level']}\n"
            f"📈 *Risk Score:* {float(vessel_info['risk_score']):.3f}\n"
            f"⚙️ *Dispatch Order:* {dispatch_order}\n"
            f"📋 *AI Recommendation:* {vessel_info['recommended_action']}\n"
            f"✅ *Status:* Dispatch Confirmed"
        )

        ok, msg = send_telegram_message(telegram_msg)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

st.markdown("---")

left, right = st.columns(2)

with left:
    if critical_alerts > 0:
        st.error(f"{critical_alerts} vessels are currently in CRITICAL state.")
    elif warning_alerts > 0:
        st.warning(f"{warning_alerts} vessels are currently under WARNING status.")
    else:
        st.success("All monitored vessels are currently in NORMAL status.")

with right:
    st.caption("SmartPort tactical view powered by Supabase live predictions.")