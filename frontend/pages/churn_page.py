import requests
import streamlit as st
import pandas as pd
from frontend.utils.export_utils import export_to_format

API_URL = "http://127.0.0.1:8000"

@st.cache_data
def get_processed_churn_results(predictions_data):
    """Caches churn prediction results and pre-calculates lowercase search index."""
    df = pd.DataFrame(predictions_data)
    # Identify searchable ID column
    id_cols = [c for c in df.columns if any(k in c.lower() for k in ["customerid", "customer_id", "userid", "user_id", "id"])]
    if id_cols:
        df['_search_id'] = df[id_cols[0]].astype(str).str.lower()
    return df

def show():
    """
    Main entry point for the Churn Prediction report page. 
    Handles dataset selection and prediction results visualization.
    """
    st.title("📉 Churn Prediction")
    st.markdown("Select an ingested dataset to view the churn prediction report.")
    st.divider()

    username = st.session_state.get("username", "")
    if not username:
        st.error("Authentication Error: Please login to access reports.")
        return

    # Fetch user's cases safely
    try:
        res = requests.get(f"{API_URL}/ingest/cases/{username}", timeout=10)
        cases_data = res.json().get("cases", []) if res.status_code == 200 else []
    except Exception:
        cases_data = []

    # Get completed churn datasets
    churn_cases = [
        c for c in cases_data 
        if c.get("task_type") == "Churn Prediction" and c.get("review_status") == "Completed"
    ]

    if not churn_cases:
        st.info(
            "No completed Churn Prediction datasets found. "
            "Go to 'Document Ingestion' to upload one."
        )
        return

    # Map labels to case IDs
    case_mapping = {
        f"{c['filename']} (ID: {c['case_id']})": c['case_id'] for c in churn_cases
    }
    
    selected_case_label = st.selectbox(
        "Select Dataset", 
        list(case_mapping.keys()), 
        key="select_churn_dataset"
    )
    
    if st.button("📊 View Report", use_container_width=True, key="btn_view_churn"):
        # Clear previous search when viewing a new report
        if "churn_user_search" in st.session_state:
            st.session_state.churn_user_search = ""
            
        case_id = case_mapping[selected_case_label]
        with st.spinner("Fetching predictive results..."):
            try:
                res = requests.get(f"{API_URL}/ingest/results/{case_id}", timeout=30)
                if res.status_code == 200:
                    st.session_state.churn_results = res.json()
                else:
                    st.error(f"Error fetching results: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    if "churn_results" in st.session_state:
        show_churn_results(st.session_state.churn_results)

def show_churn_results(data):
    """
    Renders metrics and a detailed prediction table for the selected churn dataset.
    """
    if "error" in data:
        st.error(f"Processing Error: {data['error']}")
        return

    st.success("✅ Prediction Analysis Complete!")
    
    # --- Overall Metrics ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Customers", data["total_customers"])
    c2.metric("Predicted Churn", data["predicted_churn"], delta_color="inverse")
    c3.metric("Projected Churn Rate", f"{data['churn_rate']}%", delta_color="inverse")
    st.divider()
    
    # Export Section
    st.subheader("📥 Export Prediction Report")
    df_full = get_processed_churn_results(data["predictions"])
    col_fmt, col_btn = st.columns([1, 1])
    with col_fmt:
        export_fmt = st.selectbox("Select Format", ["CSV", "Excel", "DOCX", "PDF"], key="churn_export_fmt")
    
    export_data = export_to_format(df_full, export_fmt, title="Customer Churn Prediction Report")
    
    with col_btn:
        st.write("") # Padding
        st.download_button(
            label=f"⬇️ Download as {export_fmt}",
            data=export_data,
            file_name=f"churn_report.{export_fmt.lower()}",
            mime="application/octet-stream",
            use_container_width=True,
        )

    # --- Search and Table as a Fragment (only this re-renders on search/clear) ---
    @st.fragment
    def render_churn_table():
        st.subheader("📋 Client Risk Profile")
        
        if st.session_state.get("clear_churn"):
            st.session_state.churn_q_in = ""
            st.session_state.clear_churn = False

        with st.form("churn_search_form"):
            c_in, c_search, c_clear = st.columns([3, 1, 1])
            with c_in:
                search_query_raw = st.text_input("Search ID", key="churn_q_in", label_visibility="collapsed", placeholder="Enter ID...")
            with c_search:
                st.form_submit_button("Search")
            with c_clear:
                if st.form_submit_button("Clear"):
                    st.session_state.clear_churn = True
                    st.rerun(scope="fragment")

        df_display = df_full.copy()
        
        # Apply Filtering (Fast Local)
        if search_query_raw:
            search_q = search_query_raw.strip().lower()
            if '_search_id' in df_display.columns:
                df_display = df_display[df_display['_search_id'].str.startswith(search_q)]
            else:
                # Fallback to customer_index prefix match
                df_display = df_display[df_display["customer_index"].astype(str).str.lower().str.startswith(search_q)]
        else:
            st.caption("Showing preview of first 1,000 customers. Use 'Search ID' to find specific risk profiles.")
            df_display = df_display.head(1000)

        # --- Render Table ---
        if df_display.empty and search_query_raw:
            st.warning("⚠️ No records found.")
        else:
            def style_churn_risk(row):
                if str(row.get("risk_level", "")).lower() in ["high", "medium"]:
                    return ["background-color: rgba(255, 44, 0, 0.20)"] * len(row)
                return ["background-color: rgba(0, 222, 3, 0.15)"] * len(row)

            st.dataframe(
                df_display.style.apply(style_churn_risk, axis=1), 
                use_container_width=True,
                hide_index=True
            )
    
    render_churn_table()
