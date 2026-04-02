import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pytz
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, JsCode

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amazon Returns Scanner",
    page_icon="📦",
    layout="wide"
)

# Custom CSS for Amazon Theme
st.markdown("""
    <style>
    .big-font { font-size: 24px !important; font-weight: bold; color: #FF9900; }
    .stButton>button { background-color: #FF9900; color: white; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# Session State
if 'amazon_df' not in st.session_state:
    st.session_state['amazon_df'] = None

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %I:%M:%S %p')

# -----------------------------------------------------------------------------
# Sidebar: File Upload
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("📦 Amazon Data Central")
    uploaded_file = st.file_uploader("Upload Amazon Return Report (Excel/CSV)", type=['csv', 'xlsx'])
    
    if uploaded_file:
        if st.button("🚀 Load Data"):
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                # Cleaning column names
                df.columns = df.columns.str.strip()
                
                # Force "Received" columns if they don't exist
                if 'Received' not in df.columns:
                    df['Received'] = "Not Received"
                if 'Received Timestamp' not in df.columns:
                    df['Received Timestamp'] = ""
                
                st.session_state['amazon_df'] = df
                st.success("File Loaded Successfully!")
            except Exception as e:
                st.error(f"Error: {e}")

# -----------------------------------------------------------------------------
# Main Dashboard
# -----------------------------------------------------------------------------
st.markdown('<p class="big-font">Amazon Returns Scanner</p>', unsafe_allow_html=True)

df = st.session_state.get('amazon_df')

if df is None:
    st.info("👈 Please upload your Amazon Return Report from the sidebar to begin.")
else:
    # Quick Stats
    c1, c2, c3 = st.columns(3)
    total = len(df)
    done = (df['Received'] == "Received").sum()
    c1.metric("Total Orders", total)
    c2.metric("✅ Processed", done)
    c3.metric("⏳ Pending", total - done)

    # Scanner Input
    with st.container():
        st.subheader("🎯 Scan Tracking ID")
        scan_id = st.text_input("Point your scanner here...", placeholder="Scan Tracking ID (Column K)")
        
        if scan_id:
            clean_id = str(scan_id).strip().lower()
            # Searching in Tracking ID column
            mask = df['Tracking ID'].astype(str).str.strip().str.lower() == clean_id
            
            if mask.any():
                if df.loc[mask, 'Received'].iloc[0] == "Received":
                    st.warning(f"⚠️ ID {scan_id} is already marked!")
                else:
                    df.loc[mask, 'Received'] = "Received"
                    df.loc[mask, 'Received Timestamp'] = get_ist_time()
                    st.session_state['amazon_df'] = df
                    st.success(f"✅ Marked Received: {scan_id}")
                    st.rerun()
            else:
                st.error(f"❌ Tracking ID {scan_id} not found in the file.")

    st.divider()
    
    # AgGrid Table
    st.subheader("📊 Return Details")
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationPageSize=15)
    gb.configure_default_column(sortable=True, filterable=True)
    
    # Green highlight for received items
    jscode = JsCode("""
    function(params) {
        if (params.data.Received === 'Received') {
            return { 'color': 'white', 'backgroundColor': '#2e7d32' }
        }
    };
    """)
    gb.configure_grid_options(getRowStyle=jscode)
    
    AgGrid(df, gridOptions=gb.build(), allow_unsafe_jscode=True, theme='streamlit')

    # Download Button
    st.divider()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 Download Updated Amazon Sheet", output.getvalue(), "updated_amazon_returns.xlsx")
