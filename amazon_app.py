import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pytz
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, JsCode

# -----------------------------------------------------------------------------
# 1. Page & Style Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Amazon Returns Scanner",
    page_icon="📦",
    layout="wide"
)

# Amazon Theme CSS
st.markdown("""
    <style>
    .main-title { color: #FF9900; font-size: 32px; font-weight: bold; margin-bottom: 20px; }
    .stButton>button { background-color: #FF9900; color: white; width: 100%; border-radius: 8px; font-weight: bold; }
    .stButton>button:hover { background-color: #e68a00; border: 1px solid #111; }
    .metric-card { background-color: #f3f3f3; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9900; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Initialization
# -----------------------------------------------------------------------------
if 'amazon_df' not in st.session_state:
    st.session_state['amazon_df'] = None

def get_ist_time():
    """Returns current time in IST format."""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime('%Y-%m-%d %I:%M:%S %p')

# -----------------------------------------------------------------------------
# 3. Sidebar (File Upload & Management)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Operations")
    st.info("Currently in Local Mode. Google API Integration is OFF.")
    
    uploaded_file = st.file_uploader("Upload Amazon Return Report (Excel/CSV)", type=['csv', 'xlsx'])
    
    if uploaded_file:
        if st.button("🔄 Load & Initialize Data"):
            try:
                # File reading logic
                if uploaded_file.name.endswith('.csv'):
                    temp_df = pd.read_csv(uploaded_file)
                else:
                    temp_df = pd.read_excel(uploaded_file)
                
                # Clean column names
                temp_df.columns = temp_df.columns.str.strip()
                
                # Check for Tracking ID (Expected in Column K)
                if 'Tracking ID' not in temp_df.columns:
                    st.error("❌ 'Tracking ID' column not found! Please rename Column K header to 'Tracking ID'.")
                else:
                    # Add processing columns if missing
                    if 'Received' not in temp_df.columns:
                        temp_df['Received'] = "Not Received"
                    if 'Received Timestamp' not in temp_df.columns:
                        temp_df['Received Timestamp'] = ""
                    
                    st.session_state['amazon_df'] = temp_df
                    st.success("✅ Data Loaded Successfully!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error loading file: {e}")

    if st.session_state['amazon_df'] is not None:
        st.divider()
        st.markdown("### 📥 Export Result")
        
        # Prepare Excel for download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state['amazon_df'].to_excel(writer, index=False)
        
        st.download_button(
            label="Download Updated Sheet",
            data=output.getvalue(),
            file_name=f"Amazon_Returns_{datetime.now().strftime('%d_%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        if st.button("🗑️ Reset All Scans", type="secondary"):
            st.session_state['amazon_df']['Received'] = "Not Received"
            st.session_state['amazon_df']['Received Timestamp'] = ""
            st.rerun()

# -----------------------------------------------------------------------------
# 4. Main Dashboard
# -----------------------------------------------------------------------------
st.markdown('<div class="main-title">📦 Amazon Returns Scanner</div>', unsafe_allow_html=True)

df = st.session_state.get('amazon_df')

if df is None:
    st.warning("👈 Please upload an Amazon Return file from the sidebar to start.")
else:
    # --- Metrics Section ---
    total_rows = len(df)
    received_count = (df['Received'] == "Received").sum()
    pending_count = total_rows - received_count
    
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="metric-card"><b>Total Returns</b><br><h2>{total_rows}</h2></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card" style="border-left-color: green;"><b>✅ Received</b><br><h2>{received_count}</h2></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card" style="border-left-color: red;"><b>⏳ Pending</b><br><h2>{pending_count}</h2></div>', unsafe_allow_html=True)

    st.divider()

    # --- Scanning Section ---
    st.subheader("🎯 Scan Tracking ID")
    
    # Form for faster scanning (Enter key submits)
    with st.form("scanner_form", clear_on_submit=True):
        col_input, col_btn = st.columns([4, 1])
        with col_input:
            scan_id = st.text_input("Scan barcode or type ID here...", label_visibility="collapsed")
        with col_btn:
            submit = st.form_submit_button("Mark Received")

    if submit and scan_id:
        clean_id = str(scan_id).strip().lower()
        # Case-insensitive match for Tracking ID
        mask = df['Tracking ID'].astype(str).str.strip().str.lower() == clean_id
        
        if mask.any():
            if df.loc[mask, 'Received'].iloc[0] == "Received":
                st.warning(f"⚠️ Tracking ID '{scan_id}' is ALREADY marked.")
            else:
                df.loc[mask, 'Received'] = "Received"
                df.loc[mask, 'Received Timestamp'] = get_ist_time()
                st.session_state['amazon_df'] = df
                st.success(f"✅ Successfully Marked: {scan_id}")
                st.rerun()
        else:
            st.error(f"❌ Tracking ID '{scan_id}' not found in the list!")

    # --- Data Table Section ---
    st.subheader("📊 Live Data Preview")
    
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_default_column(filterable=True, sortable=True, resizable=True)
    
    # JavaScript to highlight 'Received' rows in green
    row_style_jscode = JsCode("""
    function(params) {
        if (params.data.Received === "Received") {
            return {
                'color': 'white',
                'backgroundColor': '#2e7d32'
            }
        }
    };
    """)
    gb.configure_grid_options(getRowStyle=row_style_jscode)
    grid_options = gb.build()

    AgGrid(
        df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        theme='streamlit',
        height=500
    )
