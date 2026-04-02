import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import io
from datetime import datetime
import pytz

# -----------------------------------------------------------------------------
# 1. Page Configuration & Theme
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Amazon Returns Scanner", page_icon="📦", layout="wide")

st.markdown("""
    <style>
    .main-title { color: #FF9900; font-size: 32px; font-weight: bold; margin-bottom: 20px; }
    .stButton>button { background-color: #FF9900; color: white; width: 100%; border-radius: 8px; font-weight: bold; }
    .stButton>button:hover { background-color: #e68a00; border: 1px solid #111; }
    .metric-card { background-color: #f3f3f3; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9900; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Session State & Helpers
# -----------------------------------------------------------------------------
if 'amazon_df' not in st.session_state:
    st.session_state['amazon_df'] = None

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime('%Y-%m-%d %I:%M:%S %p')

def get_gspread_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Google Cloud Secrets missing in Streamlit Dashboard!")
        return None
    try:
        secret_data = st.secrets["gcp_service_account"]
        if isinstance(secret_data, str):
            creds_info = json.loads(secret_data)
        else:
            creds_info = dict(secret_data)
            
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
            
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        return None

# -----------------------------------------------------------------------------
# 3. Sidebar (Data Load & Sync)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ App Controls")
    
    # Default link set to the one provided
    default_link = "https://docs.google.com/spreadsheets/d/1NA-qRdPRpik-PLNpOVEpAYzj48nlc5FY2BQxXwCtB9U/edit?gid=0#gid=0"
    gsheet_url = st.text_input("Google Sheet Link:", value=default_link)
    
    if st.button("📥 Load from Google Sheet"):
        if gsheet_url:
            with st.spinner("Connecting to Google Sheets..."):
                client = get_gspread_client()
                if client:
                    try:
                        sh = client.open_by_url(gsheet_url)
                        ws = sh.sheet1
                        data = ws.get_all_records()
                        df = pd.DataFrame(data)
                        
                        # --- LICENSE PLATE NUMBER LOGIC ---
                        tracking_col = None
                        for col in df.columns:
                            # Checking for license-plate-number
                            if 'license' in str(col).lower() and 'plate' in str(col).lower():
                                tracking_col = col
                                break

                        if tracking_col is None:
                            st.error("❌ 'license-plate-number' column missing in Sheet!")
                        else:
                            # Internally rename to 'Tracking ID' so the rest of the app runs smoothly
                            df.rename(columns={tracking_col: 'Tracking ID'}, inplace=True)
                            if 'Received' not in df.columns: df['Received'] = "Not Received"
                            if 'Received Timestamp' not in df.columns: df['Received Timestamp'] = ""
                            st.session_state['amazon_df'] = df
                            st.success("✅ Data loaded from Cloud!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error loading sheet: {e}")
        else: st.warning("Paste a link first.")

    if st.session_state['amazon_df'] is not None:
        st.divider()
        st.markdown("### 💾 Save Work")
        
        if st.button("🚀 Push to Google Sheet", type="primary"):
            if gsheet_url:
                with st.spinner("Syncing to Cloud..."):
                    client = get_gspread_client()
                    if client:
                        try:
                            sh = client.open_by_url(gsheet_url)
                            ws = sh.sheet1
                            
                            # Create a copy for saving to avoid changing the live session state incorrectly
                            save_df = st.session_state['amazon_df'].copy()
                            
                            # Rename 'Tracking ID' back to the original 'license-plate-number' for the Google Sheet
                            save_df.rename(columns={'Tracking ID': 'license-plate-number'}, inplace=True)
                            
                            df_filled = save_df.fillna("").astype(str)
                            data_to_upload = [df_filled.columns.tolist()] + df_filled.values.tolist()
                            ws.update(range_name="A1", values=data_to_upload)
                            st.success("✅ Successfully synced to Google Sheet!")
                        except Exception as e:
                            st.error(f"Sync Error: {e}")
            else: st.warning("Please provide a Google Sheet link.")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df = st.session_state['amazon_df'].copy()
            export_df.rename(columns={'Tracking ID': 'license-plate-number'}, inplace=True)
            export_df.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Backup", output.getvalue(), f"Amazon_Returns_{datetime.now().strftime('%d_%m')}.xlsx")

# -----------------------------------------------------------------------------
# 4. Main Dashboard
# -----------------------------------------------------------------------------
st.markdown('<div class="main-title">📦 Amazon Returns Scanner</div>', unsafe_allow_html=True)

df = st.session_state.get('amazon_df')

if df is None:
    st.info("👈 Please load data from the Sidebar to start.")
else:
    t_rows = len(df)
    r_count = (df['Received'] == "Received").sum()
    p_count = t_rows - r_count
    
    m1, m2, m3 = st.columns(3)
    with m1: st.markdown(f'<div class="metric-card"><b>Total Orders</b><br><h2>{t_rows}</h2></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card" style="border-left-color: green;"><b>✅ Received</b><br><h2>{r_count}</h2></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card" style="border-left-color: red;"><b>⏳ Pending</b><br><h2>{p_count}</h2></div>', unsafe_allow_html=True)

    st.divider()

    st.subheader("🎯 Scan License Plate Number")
    with st.form("scanner_form", clear_on_submit=True):
        col_input, col_btn = st.columns([4, 1])
        scan_id = col_input.text_input("Scan barcode here...", label_visibility="collapsed", placeholder="Enter License Plate Number...")
        submit = col_btn.form_submit_button("Mark Received")

    if submit and scan_id:
        clean_id = str(scan_id).strip().lower()
        # Internally it's still called Tracking ID for the matching logic
        mask = df['Tracking ID'].astype(str).str.strip().str.lower() == clean_id
        
        if mask.any():
            if df.loc[mask, 'Received'].iloc[0] == "Received":
                st.warning(f"⚠️ License Plate '{scan_id}' is ALREADY marked.")
            else:
                df.loc[mask, 'Received'] = "Received"
                df.loc[mask, 'Received Timestamp'] = get_ist_time()
                st.session_state['amazon_df'] = df
                st.success(f"✅ Successfully Marked: {scan_id}")
                st.rerun()
        else:
            st.error(f"❌ License Plate '{scan_id}' not found!")

    # --- NATIVE DATA TABLE ---
    st.subheader("📊 Live Data Preview")
    
    def highlight_received(row):
        if row['Received'] == "Received":
            return ['background-color: #2e7d32; color: white'] * len(row)
        else:
            return [''] * len(row)

    # Make a copy for display to rename the column back to license-plate-number visually
    display_df = df.copy()
    display_df.rename(columns={'Tracking ID': 'license-plate-number'}, inplace=True)
    styled_df = display_df.style.apply(highlight_received, axis=1)
    
    st.dataframe(styled_df, use_container_width=True, height=500)
