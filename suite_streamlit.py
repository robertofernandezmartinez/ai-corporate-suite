import streamlit as st
import pandas as pd
from db.supabase_client import get_supabase

# Initialize the client
supabase = get_supabase()

import os
import streamlit as st

# Force port binding for Railway
port = int(os.environ.get("PORT", 8080))

st.set_page_config(
    page_title="AI Corporate Suite 2026",
    page_icon="📊",
    layout="wide"
)

st.title("🚀 AI Corporate Suite 2026")
st.subheader("Main Control Center")

# Sidebar Status
st.sidebar.success("Select a project module above")
st.sidebar.info("🤖 Telegram Bot: Online")

# Executive KPIs
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="🚢 SmartPort Alerts", value="716", delta="-2%", delta_color="inverse")

with col2:
    st.metric(label="🔧 NASA Engine Risk", value="0", delta="Stable")

with col3:
    st.metric(label="📦 Stockout Level", value="Low", delta="Optimal")

st.divider()

# Activity Log from Supabase
st.write("### 📋 Recent System Activity")
try:
    response = supabase.table("smartport_predictions").select("*").limit(10).execute()
    if response.data:
        df = pd.DataFrame(response.data)
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No data found in Supabase.")
except Exception as e:
    st.error(f"Connection error: {e}")

st.info("💡 Tip: Use the Telegram Bot for real-time mobile alerts.")