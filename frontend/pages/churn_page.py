import requests
import streamlit as st
import pandas as pd
from frontend.utils.export_utils import export_to_format

API_URL = "http://127.0.0.1:8000"

@st.cache_data(ttl=300)
def fetch_churn_data(case_id, page=1, limit=10, search=""):
    """Fetches a specific page of churn results from the backend."""
    try:
        params = {"page": page, "limit": limit, "search": search}
        res = requests.get(f"{API_URL}/ingest/results/{case_id}", params=params, timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Error fetching churn page {page}: {e}")
    return None

def show():
    """Main entry point for the Churn Prediction report page."""
    st.title("📉 Churn Prediction")
    st.markdown("Select an ingested dataset to view the churn prediction report.")
    st.divider()

    username = st.session_state.get("username", "")
    if not username:
        st.error("Authentication Error: Please login to access reports.")
        return

    try:
        res = requests.get(f"{API_URL}/ingest/cases/{username}", timeout=10)
        cases_data = res.json().get("cases", []) if res.status_code == 200 else []
    except Exception:
        cases_data = []

    churn_cases = [
        c for c in cases_data 
        if c.get("task_type") == "Churn Prediction" and c.get("review_status") == "Completed"
    ]

    if not churn_cases:
        st.info("No completed Churn Prediction datasets found.")
        return

    case_mapping = {f"{c['filename']} (ID: {c['case_id']})": c['case_id'] for c in churn_cases}
    selected_case_label = st.selectbox("Select Dataset", list(case_mapping.keys()), key="select_churn_dataset")
    
    if st.button("📊 View Report", width='stretch', key="btn_view_churn") or st.session_state.get("active_churn_case_id") == case_mapping[selected_case_label]:
        case_id = case_mapping[selected_case_label]
        
        if st.session_state.get("active_churn_case_id") != case_id:
            st.session_state.active_churn_case_id = case_id
            st.session_state.churn_page_num = 1
            st.session_state.churn_q_in = ""
            st.session_state.churn_metadata = None

        if st.session_state.churn_metadata is None:
            with st.spinner("Fetching churn summary..."):
                data = fetch_churn_data(case_id, page=1, limit=1)
                if data:
                    st.session_state.churn_metadata = data

        if st.session_state.churn_metadata:
            show_churn_results(st.session_state.active_churn_case_id, st.session_state.churn_metadata)

def show_churn_results(case_id, metadata):
    """Renders churn metrics and paginated table."""
    st.success("✅ Prediction Analysis Complete!")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Customers", metadata["total_customers"])
    c2.metric("Predicted Churn", metadata["predicted_churn"])
    c3.metric("Churn Rate", f"{metadata['churn_rate']}%")
    
    st.divider()
    render_churn_table_paginated(case_id)

def render_churn_table_paginated(case_id):
    """Renders the detailed churn table with server-side pagination."""
    @st.fragment
    def _churn_results_fragment():
        st.subheader("📋 Client Risk Profile")
        
        search_query = st.text_input("🔍 Search Customer ID", value=st.session_state.get("churn_q_in", ""), placeholder="Enter ID...")
        if search_query != st.session_state.get("churn_q_in"):
            st.session_state.churn_q_in = search_query
            st.session_state.churn_page_num = 1
            st.rerun(scope="fragment")

        page = st.session_state.get("churn_page_num", 1)
        data = fetch_churn_data(case_id, page=page, limit=10, search=search_query)
            
        if not data or "predictions" not in data or not data["predictions"]:
            st.warning("No records found.")
            return

        df_page = pd.DataFrame(data["predictions"])
        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)

        def style_risk(row):
            risk = str(row.get("risk_level", "")).lower()
            if risk == "high": return ["background-color: rgba(255, 44, 0, 0.2)"] * len(row)
            if risk == "medium": return ["background-color: rgba(255, 165, 0, 0.2)"] * len(row)
            return ["background-color: rgba(0, 222, 3, 0.15)"] * len(row)

        st.dataframe(df_page.style.apply(style_risk, axis=1), use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️ Prev", disabled=page <= 1, width="stretch", key="cp_prev"):
                st.session_state.churn_page_num -= 1
                st.rerun(scope="fragment")
        with c2:
            st.markdown(f"<p style='text-align:center'>Page {page} of {total_pages}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("Next ➡️", disabled=page >= total_pages, width="stretch", key="cp_next"):
                st.session_state.churn_page_num += 1
                st.rerun(scope="fragment")
                
    _churn_results_fragment()
