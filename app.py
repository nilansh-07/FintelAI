
import streamlit as st
import subprocess
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import tempfile
from pathlib import Path
import json
import re

# Load environment variables
load_dotenv()

# --- Configuration & Constants ---
PAGE_CONFIG = {
    "page_title": "Fintel AI | Advanced Document Analytics",
    "page_icon": "📊",
    "layout": "wide"
}

# Define the fields and color schemes for each document type
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
        "fields": ["Invoice Amount", "Tax Amount", "Total Amount", "Discount Amount"],
        "color_scale": "Oranges"
    },

    "Profit and Loss": {
        "fields": ["Revenue", "Expenses", "Net Profit", "Gross Profit", "Operating Profit"],
        "color_scale": "Reds"
    }
}

# --- Helper Classes ---

class DocumentProcessor:
    def __init__(self):
        # We don't store the key here; we check it at runtime from env for security
        pass

    def _sanitize_json_output(self, text):
        """
        Robustly attempts to extract valid JSON from the OCR output string.
        AI sometimes returns text before/after the JSON, this cleans it up.
        """
        try:
            # 1. Try direct parsing
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        try:
            # 2. Extract JSON from markdown code blocks (```json ... ```)
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            
            # 3. Find the first '{' and last '}'
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = text[start:end]
                return json.loads(json_str)
        except Exception:
            pass
            
        return {}

    def run_ocr(self, file_path, fields):
        """Runs the Node.js OCR script securely."""
        
        # Check for API Key
        if not os.getenv("GROQ_API_KEY"):
            st.error("❌ GROQ_API_KEY not found. Please set it in your .env file.")
            return None

        # Construct a strict prompt for JSON output
        # We define the structure so the AI knows exactly what to return
        json_structure = {field: "number" for field in fields}
        prompt = (
            f"Analyze this document image. Extract the following fields: {', '.join(fields)}. "
            f"Return the output strictly as a valid JSON object with this structure: {json.dumps(json_structure)}. "
            "Do not include currency symbols (like $, ₹) or commas in the numbers. "
            "If a field is not found in the document, set its value to 0."
        )

        try:
            # Pass the current environment (with GROQ_API_KEY) to the subprocess
            env = os.environ.copy()

            # Call the Node.js script
            # Arguments: node script_name file_path prompt
            result = subprocess.run(
                ['node', 'ocrScript.js', file_path, prompt],
                capture_output=True,
                text=True,
                env=env,
                timeout=60 # 60 second timeout
            )

            if result.returncode != 0:
                st.error(f"OCR Engine Error: {result.stderr}")
                return None

            # Parse the output
            return self._sanitize_json_output(result.stdout)

        except subprocess.TimeoutExpired:
            st.error("OCR process timed out. Please try a smaller file.")
            return None
        except Exception as e:
            st.error(f"System Error: {str(e)}")
            return None

def render_charts(df, doc_type):
    """Generates interactive Plotly charts."""
    if df.empty:
        return

    config = DOCUMENT_CONFIGS.get(doc_type, {})
    
    # Ensure values are numeric and handle missing data
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce').fillna(0)
    
    # Filter out zero values for the Donut chart to look cleaner
    df_non_zero = df[df['Value'] > 0]

    col1, col2 = st.columns(2)

    with col1:
        # Interactive Donut Chart
        if not df_non_zero.empty:
            fig_pie = px.pie(
                df_non_zero, 
                values='Value', 
                names='Field', 
                title=f"{doc_type} Distribution",
                hole=0.4,
                color_discrete_sequence=getattr(px.colors.sequential, config.get('color_scale', 'Blues'))
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No non-zero values to display in chart.")

    with col2:
        # Interactive Bar Chart
        fig_bar = px.bar(
            df, 
            x='Field', 
            y='Value', 
            text_auto='.2s', # Auto-format numbers (e.g. 1.5k)
            title=f"{doc_type} Breakdown",
            color='Value',
            color_continuous_scale=config.get('color_scale', 'Blues')
        )
        fig_bar.update_layout(xaxis_title="", yaxis_title="Amount")
        st.plotly_chart(fig_bar, use_container_width=True)

# --- Main Application ---

def main():
    st.set_page_config(**PAGE_CONFIG)
    
    # Custom CSS for better aesthetics
    st.markdown("""
        <style>
        .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
        .block-container { padding-top: 2rem; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📄 FintelAI")
    st.markdown("**Advanced Financial Document Intelligence** | Powered by Groq Llama 4 Maverick")

    processor = DocumentProcessor()

    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        doc_type = st.selectbox("Select Document Type", list(DOCUMENT_CONFIGS.keys()))
        
        st.divider()
        st.markdown("### 📂 Upload")
        uploaded_files = st.file_uploader(
            "Upload Images (JPG, PNG)", 
            type=["png", "jpg", "jpeg"], 
            accept_multiple_files=True
        )
        
        st.divider()
        process_btn = st.button("🚀 Analyze Documents", type="primary", use_container_width=True)
        
        # Debug Info
        st.caption(f"Extracting: {', '.join(DOCUMENT_CONFIGS[doc_type]['fields'][:3])}...")

    # --- Session State Management ---
    # This keeps data persistent when you interact with tabs or charts
    if 'data' not in st.session_state:
        st.session_state.data = None
    if 'current_doc_type' not in st.session_state:
        st.session_state.current_doc_type = doc_type

    # --- Processing Logic ---
    if process_btn and uploaded_files:
        # Reset state if new analysis starts
        st.session_state.data = None 
        st.session_state.current_doc_type = doc_type
        
        all_data = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, file in enumerate(uploaded_files):
            status_text.text(f"Processing {file.name}...")
            
            # Save uploaded file strictly to a temp path
            # We use delete=False to ensure Node.js can read it, then we manually delete
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp:
                tmp.write(file.getvalue())
                tmp_path = tmp.name

            try:
                # Run OCR
                extracted_json = processor.run_ocr(tmp_path, DOCUMENT_CONFIGS[doc_type]['fields'])
                
                if extracted_json:
                    # Add metadata
                    row = extracted_json.copy()
                    row['Document'] = file.name
                    all_data.append(row)
                else:
                    st.warning(f"Could not extract valid data from {file.name}")
                    
            except Exception as e:
                st.error(f"Error processing {file.name}: {e}")
            finally:
                # Cleanup temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            # Update progress
            progress_bar.progress((idx + 1) / len(uploaded_files))

        status_text.empty()
        progress_bar.empty()

        if all_data:
            # Create DataFrame
            df = pd.DataFrame(all_data)
            # Reorder columns: Document first
            cols = ['Document'] + [c for c in df.columns if c != 'Document']
            st.session_state.data = df[cols]
            st.success("Analysis Complete!")
        else:
            st.error("No data extracted. Please check the document quality.")

    # --- Dashboard Display ---
    if st.session_state.data is not None:
        df = st.session_state.data
        current_doc = st.session_state.current_doc_type
        
        st.divider()
        
        # 1. High-level Metrics (Aggregates)
        st.subheader("📈 Summary Metrics")
        numeric_cols = df.select_dtypes(include=['float64', 'int64', 'int']).columns
        
        if not numeric_cols.empty:
            cols = st.columns(min(len(numeric_cols), 4))
            for i, col in enumerate(numeric_cols[:4]):
                total_val = df[col].sum()
                cols[i].metric(label=f"Total {col}", value=f"{total_val:,.2f}")

        # 2. Tabs Interface
        tab1, tab2, tab3 = st.tabs(["📊 Visual Analytics", "📋 Detailed Data", "📥 Export"])

        with tab1:
            st.markdown(f"### {current_doc} Insights")
            # Melt DataFrame for Plotly (Wide -> Long format)
            # This allows us to plot multiple fields easily
            df_melted = df.melt(id_vars=['Document'], var_name='Field', value_name='Value')
            render_charts(df_melted, current_doc)

        with tab2:
            st.markdown("### Raw Data Table")
            st.dataframe(
                df, 
                use_container_width=True,
                column_config={
                    "Document": st.column_config.TextColumn("Document Name"),
                }
            )

        with tab3:
            st.markdown("### Export Results")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Report as CSV",
                data=csv,
                file_name=f"fintel_{current_doc.lower().replace(' ', '_')}_report.csv",
                mime="text/csv",
                key='download-csv'
            )

if __name__ == "__main__":
    main()