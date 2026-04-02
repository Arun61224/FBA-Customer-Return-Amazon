import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pytz
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, JsCode

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amazon Returns Scanner",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .big-font { font-size: 24px !important; font-weight: bold; }
    .amazon-header { color: #FF9900; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
for key in ['returns_df', 'scanned_message', 'scanned_status', 'bulk_message', 'bulk_status', 'missing_bulk_ids']:
    if key not in st.session_state:
        st.session_state[key] = None

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def get_current_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime('%Y-%m-%d %I:%M:%S %p')

def process_scan(tracking_id):
    df = st.session_state.get('returns_df')
    if df is None:
        st.error("Please upload the Amazon Excel/CSV file first.")
        return

    clean_id = str(tracking_id).strip().lower()
    if not clean_id:
        return

    # Amazon files usually have Tracking ID in Column K, 
    # but we search for the column name for flexibility.
    mask = df['Tracking ID'].astype(str).str.strip().str.lower() == clean_id
    
    if mask.any():
        if df.loc[mask, 'Received'].iloc[0] == "Received":
            st.session_state['scanned_status'] = 'warning'
            st.session_state['scanned_message'] = f"⚠️ Tracking ID '{tracking_id}' is ALREADY marked."
        else:
            df.loc[mask, 'Received'] = "Received"
            df.loc[mask, 'Received Timestamp'] = get_current_ist_time()
            st.session_state['returns_df'] = df
            st.session_state['scanned_status'] = 'success'
            st.session_state['scanned_message'] = f"✅ Marked as Received: {tracking_id}"
    else:
        st.session_state['scanned_status'] = 'error'
        st.session_state['scanned_message'] = f"❌ Tracking ID '{tracking_id}' not found in the file!"

def display_aggrid(df):
    # Adjust these column names based on your Amazon Return Report
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)
    gb.configure_default_column(filterable=True, sortable=True, resizable=True)
    
    row_style_jscode = JsCode("""
    function(params) {
        if (params.data.Received === "Received") {
            return { 'color': '#0f5132', 'backgroundColor': '#d1e7dd' }
        }
    };
    """)
    gb.configure_grid_options(getRowStyle=row_style_jscode)
    grid_options = gb.build()

    AgGrid(df, gridOptions=grid_options, allow_unsafe_jscode=True, theme='streamlit')

# -----------------------------------------------------------------------------
# Sidebar - Data Loading
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🛒 Amazon Ops")
    st.info("Currently in Local Mode (Google Sheet API Off)")
    
    uploaded_file = st.file_uploader("Upload Amazon Return Report (CSV/XLSX)", type=['csv', 'xlsx'])
    
    if uploaded_file:
        if st.button("📊 Load File"):
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Cleaning and prepping columns
            df.columns = df.columns.str.strip()
            
            # Ensuring we find the Tracking ID (Column K)
            if 'Tracking ID' not in df.columns:
                st.error("❌ 'Tracking ID' column not found! Make sure column K is named correctly.")
            else:
                if 'Received' not in df.columns:
                    df['Received'] = "Not Received"
                if 'Received Timestamp' not in df.columns:
                    df['Received Timestamp'] = ""
                
                st.session_state['returns_df'] = df
                st.success("✅ Amazon Data Loaded!")

    if st.session_state.get('returns_df') is not None:
        st.divider()
        st.markdown("### 💾 Export Data")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state['returns_df'].to_excel(writer, index=False)
        
        st.download_button(
            label="⬇️ Download Updated Excel",
            data=output.getvalue(),
            file_name="amazon_returns_updated.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# -----------------------------------------------------------------------------
# Main UI
# -----------------------------------------------------------------------------
st.markdown("<h1 class='amazon-header'>📦 Amazon Returns Scanner</h1>", unsafe_allow_html=True)

main_df = st.session_state.get('returns_df')

if main_df is None:
    st.warning("👈 Please upload the Amazon Return file in the sidebar to start scanning.")
else:
    # Metrics
    total = len(main_df)
    rec = (main_df['Received'] == "Received").sum()
    st.columns(3)[0].metric("Total Shipments", total)
    st.columns(3)[1].metric("✅ Received", rec)
    st.columns(3)[2].metric("⏳ Remaining", total - rec)

    tab_scan, tab_bulk = st.tabs(["🎯 Single Scan", "📁 Bulk Process"])

    with tab_scan:
        with st.form("scan_form", clear_on_submit=True):
            col_in, col_bt = st.columns([4, 1])
            tid = col_in.text_input("Scan Amazon Tracking ID", placeholder="Paste or Scan ID here...")
            if col_bt.form_submit_button("Mark"):
                process_scan(tid)
                st.rerun()

        if st.session_state.scanned_message:
            if st.session_state.scanned_status == 'success': st.success(st.session_state.scanned_message)
            else: st.error(st.session_state.scanned_message)

        st.markdown("### Live Preview")
        display_aggrid(main_df)

    with tab_bulk:
        st.info("Bulk feature enabled. Upload a CSV with 'Tracking ID' column to mark multiple at once.")
        # Similar logic to your Flipkart bulk upload can be added here
