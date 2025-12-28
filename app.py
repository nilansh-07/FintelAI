import streamlit as st
import subprocess
import os
import pandas as pd
import plotly.express as px # type: ignore
import plotly.graph_objects as go # type: ignore
from dotenv import load_dotenv
import tempfile
from pathlib import Path
import json
import re

# Load environment variables
load_dotenv()

# --- Page Configuration ---
st.set_page_config(
    page_title="Fintel AI | Llama 4 Maverick",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Configuration & Constants ---
DOCUMENT_CONFIGS = {
    "Salary Slip": {
        "fields": ["Basic Salary", "HRA", "DA", "PF", "Net Salary", "Gross Salary"],
        "color_scale": "Blues"
    },
    "Bank Statement": {
        "fields": ["Opening Balance", "Closing Balance", "Total Credits", "Total Debits"],
        "color_scale": "Greens"
    },
    "Balance Sheet": {
        "fields": ["Total Assets", "Total Liabilities", "Current Assets", "Current Liabilities", "Net Worth"],
        "color_scale": "Purples"
    },
    "Invoice": {
        "fields": ["Invoice Amount", "Tax Amount", "Total Amount", "Discount Amount", "Invoice Number"],
        "color_scale": "Oranges"
    },
    "Profit and Loss": {
        "fields": ["Revenue", "Expenses", "Net Profit", "Gross Profit", "Operating Profit"],
        "color_scale": "Reds"
    }
}

# --- UI Components (Header & Footer) ---

def setup_header():
    """Renders a styled header using HTML/CSS."""
    st.markdown("""
        <style>
            /* Main Header Style */
            .main-header {
                background: linear-gradient(to right, #4b6cb7, #182848);
                padding: 20px;
                border-radius: 10px;
                color: white;
                text-align: center;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .main-header h1 {
                margin: 0;
                font-family: 'Helvetica Neue', sans-serif;
                font-size: 2.5rem;
                font-weight: 700;
                color: #ffffff;
            }
            .main-header p {
                margin: 5px 0 0;
                font-size: 1.1rem;
                opacity: 0.9;
                color: #f0f2f6;
            }
        </style>
        <div class="main-header">
            <h1>📄 Fintel AI</h1>
            <p>Advanced Financial Document Intelligence • Powered by Llama 4 Scout</p>
        </div>
    """, unsafe_allow_html=True)

def setup_footer():
    """Renders a styled footer fixed at the bottom."""
    st.markdown("""
        <style>
            .footer {
                position: fixed;
                left: 0;
                bottom: 0;
                width: 100%;
                background-color: #0e1117;
                color: #888;
                text-align: center;
                padding: 10px;
                font-size: 14px;
                border-top: 1px solid #333;
                z-index: 1000;
            }
            .footer a {
                color: #4b6cb7;
                text-decoration: none;
                font-weight: bold;
            }
            .footer a:hover {
                text-decoration: underline;
            }
            /* Add padding to body to prevent footer from covering content */
            .block-container {
                padding-bottom: 80px;
            }
        </style>
        <div class="footer">
            <p>
                Developed by <b>Nilansh Kumar</b> | 
                <a href="https://groq.com" target="_blank">Groq AI</a> Powered | 
                &copy; 2025 Fintel AI
            </p>
        </div>
    """, unsafe_allow_html=True)

# --- Helper Classes ---

class DocumentProcessor:
    def _sanitize_json_output(self, text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != 0:
                return json.loads(text[start:end])
        except Exception:
            pass
        return {}

    def run_ocr(self, file_path, fields):
        if not os.getenv("GROQ_API_KEY"):
            st.error("❌ GROQ_API_KEY is missing in .env file.")
            return None

        json_structure = {field: "number" for field in fields}
        prompt = (
            f"Analyze this document image. Extract these exact fields: {', '.join(fields)}. "
            f"Return a strict JSON object with this structure: {json.dumps(json_structure)}. "
            "Do not include currency symbols ($ or ₹) or commas in numbers. "
            "If a field is not visible, return 0."
        )

        try:
            env = os.environ.copy()
            result = subprocess.run(
                ['node', 'ocrScript.js', file_path, prompt],
                capture_output=True,
                text=True,
                env=env,
                timeout=60
            )

            if result.returncode != 0:
                st.error(f"OCR Failed: {result.stderr}")
                return None

            return self._sanitize_json_output(result.stdout)
        except subprocess.TimeoutExpired:
            st.error("⏳ OCR process timed out.")
            return None
        except Exception as e:
            st.error(f"System Error: {str(e)}")
            return None

def render_charts(df, doc_type):
    if df.empty:
        return

    config = DOCUMENT_CONFIGS.get(doc_type, {})
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce').fillna(0)
    df_nonzero = df[df['Value'] > 0]

    col1, col2 = st.columns(2)

    with col1:
        if not df_nonzero.empty:
            fig_pie = px.pie(
                df_nonzero, 
                values='Value', 
                names='Field', 
                title=f"Distribution Analysis",
                hole=0.4,
                color_discrete_sequence=getattr(px.colors.sequential, config.get('color_scale', 'Blues'))
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No numeric data available for Distribution chart.")

    with col2:
        fig_bar = px.bar(
            df, 
            x='Field', 
            y='Value', 
            text_auto='.2s',
            title=f"Field Breakdown",
            color='Value',
            color_continuous_scale=config.get('color_scale', 'Blues')
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# --- Main Application ---

def main():
    # 1. Render Header
    setup_header()

    processor = DocumentProcessor()

    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Settings")
        doc_type = st.selectbox("Document Type", list(DOCUMENT_CONFIGS.keys()))
        st.markdown("---")
        uploaded_files = st.file_uploader("Upload Document (Image)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        st.markdown("---")
        process_btn = st.button("🚀 Analyze Now", type="primary", use_container_width=True)

    # --- Session State ---
    if 'data' not in st.session_state:
        st.session_state.data = None

    # --- Processing ---
    if process_btn and uploaded_files:
        all_data = []
        progress_bar = st.progress(0)
        status = st.empty()
        
        for idx, file in enumerate(uploaded_files):
            status.markdown(f"**Processing:** `{file.name}`...")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp:
                tmp.write(file.getvalue())
                tmp_path = tmp.name

            try:
                data = processor.run_ocr(tmp_path, DOCUMENT_CONFIGS[doc_type]['fields'])
                if data:
                    row = data.copy()
                    row['Document'] = file.name
                    all_data.append(row)
                else:
                    st.warning(f"Could not extract data from {file.name}")     
            finally:
                os.unlink(tmp_path)
            
            progress_bar.progress((idx + 1) / len(uploaded_files))

        status.empty()
        progress_bar.empty()

        if all_data:
            st.session_state.data = pd.DataFrame(all_data)
            cols = ['Document'] + [c for c in st.session_state.data.columns if c != 'Document']
            st.session_state.data = st.session_state.data[cols]
            st.success("Analysis Complete!")

    # --- Dashboard ---
    if st.session_state.data is not None:
        df = st.session_state.data
        
        st.divider()
        st.subheader("Key Financial Metrics")
        numeric_cols = df.select_dtypes(include=['float64', 'int64', 'int']).columns
        if not numeric_cols.empty:
            cols = st.columns(min(len(numeric_cols), 4))
            for i, col in enumerate(numeric_cols[:4]):
                total = df[col].sum()
                cols[i].metric(col, f"{total:,.2f}")

        tab1, tab2, tab3 = st.tabs(["📊 Visuals", "📋 Data Table", "📥 Export"])

        with tab1:
            df_melted = df.melt(id_vars=['Document'], var_name='Field', value_name='Value')
            render_charts(df_melted, doc_type)

        with tab2:
            st.dataframe(df, use_container_width=True)

        with tab3:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "fintel_report.csv", "text/csv", type="primary")

    # 2. Render Footer
    setup_footer()

if __name__ == "__main__":
    main()