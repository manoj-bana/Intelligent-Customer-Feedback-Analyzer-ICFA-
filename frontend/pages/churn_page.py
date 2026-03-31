import requests
import streamlit as st
import pandas as pd
from frontend.utils.export_utils import export_to_format

API_URL = "http://127.0.0.1:8000"

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
        case_id = case_mapping[selected_case_label]
        with st.spinner("Preparing predictive report..."):
            try:
                res = requests.get(f"{API_URL}/ingest/results/{case_id}", timeout=30)
                if res.status_code == 200:
                    results_data = res.json()
                    st.session_state.churn_results = results_data
                    # One-time processing
                    st.session_state.processed_churn_df = pd.DataFrame(results_data.get("predictions", []))
                else:
                    st.error(f"Error fetching results: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    if "churn_results" in st.session_state:
        show_churn_results(
            st.session_state.churn_results,
            st.session_state.get("processed_churn_df")
        )

def show_churn_results(data, df):
    """
    Renders metrics and a detailed prediction table using optimized dataframes.
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
    df_churn = df
    col_fmt, col_btn = st.columns([1, 1])
    with col_fmt:
        export_fmt = st.selectbox("Select Format", ["CSV", "Excel", "DOCX", "PDF"], key="churn_export_fmt")
    
    export_data = export_to_format(df_churn, export_fmt, title="Customer Churn Prediction Report")
    
    with col_btn:
        st.write("") # Padding
        st.download_button(
            label=f"⬇️ Download as {export_fmt}",
            data=export_data,
            file_name=f"churn_report.{export_fmt.lower()}",
            mime="application/octet-stream",
            use_container_width=True,
        )

    st.divider()

    # --- Detailed Data Grid ---
    render_churn_table_fragment(df)

@st.fragment
def render_churn_table_fragment(df):
    """
    Renders the churn prediction list in an isolated fragment for high-speed pagination.
    Only this block reruns when navigating between pages.
    """
    st.subheader("Individual Customer Risk Profile")

    # --- Pagination Logic ---
    items_per_page = 10
    total_items = len(df)
    total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1

    if "churn_page_num" not in st.session_state:
        st.session_state.churn_page_num = 1

    # Clamp page number
    if st.session_state.churn_page_num > total_pages:
        st.session_state.churn_page_num = total_pages
    if st.session_state.churn_page_num < 1:
        st.session_state.churn_page_num = 1

    # Pagination Controls (Top)
    cp1, cp2, cp3 = st.columns([1, 2, 1])
    with cp1:
        if st.button("⬅️ Previous", disabled=st.session_state.churn_page_num <= 1, key="cp_prev", use_container_width=True):
            st.session_state.churn_page_num -= 1
            try: st.rerun(scope="fragment")
            except: st.rerun()
    with cp2:
        pass # Placeholder
    with cp3:
        if st.button("Next ➡️", disabled=st.session_state.churn_page_num >= total_pages, key="cp_next", use_container_width=True):
            st.session_state.churn_page_num += 1
            try: st.rerun(scope="fragment")
            except: st.rerun()

    start_idx = (st.session_state.churn_page_num - 1) * items_per_page
    end_idx = start_idx + items_per_page

    with cp2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 5px;'>"
            f"Page <b>{st.session_state.churn_page_num}</b> of <b>{total_pages}</b>"
            f"<br><small>{total_items} customers total</small></div>", 
            unsafe_allow_html=True
        )

    def style_churn_risk(row):
        """
        Styles table rows based on churn prediction for high-visibility risk flagging.
        """
        if row["churn_prediction"] == "Yes":
            return ["background-color: rgba(255, 44, 0, 0.15)"] * len(row)
        return ["background-color: rgba(0, 222, 3, 0.10)"] * len(row)

    df_page = df.iloc[start_idx:end_idx]
    st.dataframe(
        df_page.style.apply(style_churn_risk, axis=1), 
        use_container_width=True,
        hide_index=True
    )
