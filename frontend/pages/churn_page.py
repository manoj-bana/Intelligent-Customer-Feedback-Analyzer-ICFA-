import requests
import streamlit as st
import pandas as pd
from frontend.utils.export_utils import export_to_format

import os
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def fetch_churn_data(case_id, page=1, limit=10, search="", risk_level=None):
    try:
        res = requests.get(
            f"{API_URL}/ingest/results/{case_id}",
            params={"page": page, "limit": limit, "search": search, "risk_level": risk_level},
            headers=get_headers(),
            timeout=10
        )
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def show():
    """
    Main entry point for the Churn Prediction report page. 
    Synchronized with live results via 5s polling.
    """
    # Silent 5s heartbeat to catch new background report completions
    # st_autorefresh(interval=5000, key="report_churn_page_sync")
    
    st.title("📉 Churn Prediction")
    st.markdown("Select an ingested dataset to view the churn prediction report.")
    st.divider()

    username = st.session_state.get("username", "")
    if not username:
        st.error("Authentication Error: Please login to access reports.")
        return

    # Fetch user's cases safely (Fresh every heartbeat)
    try:
        res = requests.get(f"{API_URL}/ingest/cases/{username}", headers=get_headers(), timeout=10)
        cases_data = res.json().get("cases", []) if res.status_code == 200 else []
    except Exception:
        cases_data = []

    # Get completed churn datasets - SORTED LATEST FIRST
    churn_cases = sorted([
        c for c in cases_data 
        if c.get("task_type") == "Churn Prediction" and str(c.get("review_status")).lower() == "completed"
    ], key=lambda x: x.get("id", 0), reverse=True)

    if not churn_cases:
        st.info(
            "No completed Churn Prediction datasets found. "
            "Go to 'Document Ingestion' to start an analysis."
        )
        return

    # Map labels to case IDs (Maintaining NEWEST FIRST order)
    case_mapping = {
        f"🆕 {c['filename']} (ID: {c['case_id']})" if i == 0 else f"{c['filename']} (ID: {c['case_id']})": c['case_id'] 
        for i, c in enumerate(churn_cases)
    }
    
    selected_case_label = st.selectbox(
        "Select Dataset", 
        list(case_mapping.keys()), 
        key="select_churn_dataset"
    )
    
    if st.button("📊 View Report", width='stretch', key="btn_view_churn") or st.session_state.get("active_churn_case_id") == case_mapping[selected_case_label]:
        case_id = case_mapping[selected_case_label]
        
        if st.session_state.get("active_churn_case_id") != case_id:
            st.session_state.active_churn_case_id = case_id
            st.session_state.churn_page_num = 1
            st.session_state.churn_q_in = ""
            st.session_state.churn_risk_filter = "All"
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
        page = st.session_state.get("churn_page_num", 1)
        risk_filter = st.session_state.get("churn_risk_filter", "All")
        search_query = st.session_state.get("churn_q_in", "")
        
        # Fetch data first to get counts and current page
        data = fetch_churn_data(case_id, page=page, limit=10, search=search_query, risk_level=risk_filter)
        
        if not data:
            st.warning("Failed to fetch data.")
            return

        # Risk Level Filter Buttons
        risk_counts = data.get("risk_counts", {"low": 0, "medium": 0, "high": 0, "safe": 0})
        active_filter = st.session_state.get("churn_risk_filter", "All")
        
        st.subheader("📋 Client Risk Profile")
        cols = st.columns([1, 1.2, 1.2, 1.2, 1])
        with cols[1]:
            if st.button(f"Low ({risk_counts.get('low', 0)})", use_container_width=True, 
                         type="primary" if active_filter == "Low" else "secondary"):
                st.session_state.churn_risk_filter = "Low"
                st.session_state.churn_page_num = 1
                st.rerun()
        with cols[2]:
            if st.button(f"Medium ({risk_counts.get('medium', 0)})", use_container_width=True,
                         type="primary" if active_filter == "Medium" else "secondary"):
                st.session_state.churn_risk_filter = "Medium"
                st.session_state.churn_page_num = 1
                st.rerun()
        with cols[3]:
            if st.button(f"High ({risk_counts.get('high', 0)})", use_container_width=True,
                         type="primary" if active_filter == "High" else "secondary"):
                st.session_state.churn_risk_filter = "High"
                st.session_state.churn_page_num = 1
                st.rerun()
        
        # Add a reset filter button if something is selected
        if active_filter != "All":
            c1, c2, c3 = st.columns([2, 1, 2])
            with c2:
                if st.button("Clear Filter", icon="✖️", use_container_width=True):
                    st.session_state.churn_risk_filter = "All"
                    st.session_state.churn_page_num = 1
                    st.rerun()

        st.divider()

        search_query_new = st.text_input("🔍 Search Customer ID", value=search_query, placeholder="Enter ID...")
        if search_query_new != search_query:
            st.session_state.churn_q_in = search_query_new
            st.session_state.churn_page_num = 1
            st.rerun()

        if "predictions" not in data or not data["predictions"]:
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
                st.rerun()
        with c2:
            st.markdown(f"<p style='text-align:center'>Page {page} of {total_pages}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("Next ➡️", disabled=page >= total_pages, width="stretch", key="cp_next"):
                st.session_state.churn_page_num += 1
                st.rerun()
                
    _churn_results_fragment()
