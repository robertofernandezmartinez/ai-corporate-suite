import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import plotly.express as px

# =====================================================================
# 1. PAGE CONFIGURATION
# =====================================================================
st.set_page_config(
    page_title="SmartPort AI | Command Center",
    page_icon="⚓",
    layout="wide"
)

# =====================================================================
# 2. DATA LOADING (via Streamlit Secrets)
# =====================================================================
@st.cache_data(ttl=600)  # Caches data for 10 minutes to improve speed
def load_port_data():
    try:
        # Spreadsheet ID from your project
        SHEET_ID = "1aTJLlg4YNT77v1PLQccKl8ZCADBJN0U8kncTBvf43P0"
        
        # Load credentials from Secrets (The "GCP Service Account" block)
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Open the specific sheet
        sheet = client.open_by_key(SHEET_ID).sheet1
        records = sheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return pd.DataFrame()

# Initial data load
df = load_port_data()

# =====================================================================
# 3. MAIN DASHBOARD LAYOUT
# =====================================================================
st.title("⚓ SmartPort AI | Command Center")
st.markdown("---")

if not df.empty:
    # Top Row: KPIs
    total_vessels = len(df)
    critical_alerts = len(df[df['risk_level'].str.upper() == 'CRITICAL'])
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Vessels", total_vessels)
    m2.metric("Critical Alerts", critical_alerts, delta_color="inverse")
    m3.metric("System Status", "Live", "Cloud Connected")

    st.write("") # Spacer

    # Middle Row: Visualizations and Table
    col_table, col_side = st.columns([2, 1])

    with col_table:
        st.subheader("Live Vessel Risk Monitor")
        # Selecting key columns from your Sheets (ensure these match your headers)
        cols_to_show = ['vessel_id', 'risk_score', 'risk_level', 'recommended_action']
        st.dataframe(df[cols_to_show], use_container_width=True, hide_index=True)

    # =====================================================================
    # 4. ACTION CENTER (Sidebar & Control)
    # =====================================================================
    with col_side:
        st.subheader("🕹️ Tactical Control")
        
        # Dropdown populated with REAL IDs from Sheets
        target_ship = st.selectbox("Select Target Vessel:", df['vessel_id'].unique())
        
        # Retrieve information for the selected vessel
        ship_info = df[df['vessel_id'] == target_ship].iloc[0]
        
        st.info(f"**AI Recommendation:**\n{ship_info['recommended_action']}")
        
        dispatch_order = st.selectbox("Select Dispatch Order:", [
            "Immediate Berth Reassignment",
            "Priority Inspection Hold",
            "AIS Protocol Synchronization",
            "Manual Port Clearance"
        ])
        
        if st.button("Execute & Notify Telegram"):
            # Fetch Telegram keys from Secrets
            token = st.secrets["TELEGRAM_TOKEN"]
            chat_id = st.secrets["TELEGRAM_CHAT_ID"]
            
            # Construct professional notification
            telegram_msg = (
                f"🚨 *SMARTPORT OPERATIONAL COMMAND*\n\n"
                f"🚢 *Vessel:* {target_ship}\n"
                f"⚙️ *Order:* {dispatch_order}\n"
                f"📋 *Ref Action:* {ship_info['recommended_action']}\n"
                f"✅ *Status:* Dispatch Confirmed"
            )
            
            # Send API Request
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": telegram_msg, "parse_mode": "Markdown"}
            
            try:
                response = requests.post(url, json=payload)
                if response.status_code == 200:
                    st.toast(f"Notification sent for {target_ship}")
                    st.success("Telegram Dispatch Successful")
                else:
                    st.error("Failed to notify Telegram")
            except Exception as e:
                st.error(f"Telegram Connection Error: {e}")

else:
    st.warning("No data found. Please check your Spreadsheet connection and Secrets configuration.")

st.sidebar.markdown("---")
st.sidebar.caption("SmartPort AI v1.0 | Data-Driven Decisions")