import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

def show():
    """
    Main entry point for the dashboard. Handles sidebar navigation and page routing.
    """
    st.sidebar.title(f"👤 {st.session_state.username}")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigate",
        ["🏠 Home", "☁️ Document Ingestion", "📊 Reports"]
    )

    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.token = ""
        st.rerun()

    if page == "🏠 Home":
        show_home()
    elif page == "☁️ Document Ingestion":
        from frontend.pages import ingestion
        ingestion.show()
    elif page == "📊 Reports":
        st.title("📊 Analysis Reports")
        st.markdown("Select a report module:")
        tab1, tab2 = st.tabs(["💬 Sentiment Analysis", "📉 Churn Prediction"])
        with tab1:
            from frontend.pages import feedback_page
            feedback_page.show()
        with tab2:
            from frontend.pages import churn_page
            churn_page.show()

def show_home():
    """
    Renders the Home page of the dashboard with global KPIs and a data grid of user cases.
    """
    st.title("📊 ICFA Dashboard")
    st.markdown("### Intelligent Customer Feedback Analyzer")
    st.divider()

    username = st.session_state.get("username", "")

    # --- Data Fetching ---
    try:
        res = requests.get(f"{API_URL}/ingest/cases/{username}", timeout=10)
        cases_data = res.json().get("cases", []) if res.status_code == 200 else []
    except Exception:
        cases_data = []

    # --- KPI Calculations ---
    total_datasets = len(cases_data)
    pending = sum(1 for c in cases_data if "Pending" in c["review_status"])
    completed = total_datasets - pending
    needs_attention = sum(1 for c in cases_data if "Error" in c["review_status"])

    success_rate = 0
    if total_datasets > 0:
        success_rate = round((completed / total_datasets * 100))
        
    error_cases = [c for c in cases_data if "Error" in c["review_status"]]

    # --- Metric Display ---
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(
            "Total Datasets", 
            total_datasets, 
            delta=f"{success_rate}% success rate" if total_datasets > 0 else "No uploads yet"
        )
    with kpi2:
        st.metric(
            "Pending Review", 
            pending, 
            delta=f"{pending} awaiting queue" if pending > 0 else "Queue clear", 
            delta_color="inverse"
        )
    with kpi3:
        st.metric(
            "Reviews Complete", 
            completed, 
            delta=f"{success_rate}% of total uploads"
        )
    with kpi4:
        st.metric(
            "Needs Attention", 
            needs_attention, 
            delta=f"{len(error_cases)} failed jobs" if needs_attention > 0 else "All healthy", 
            delta_color="inverse" if needs_attention > 0 else "normal"
        )

    st.divider()
    
    # --- "My Cases" Data Grid ---
    st.subheader("My Cases")
    
    if not cases_data:
        st.info("No cases found. Navigate to `Document Ingestion` to upload your first dataset!")
    else:
        df_cases = pd.DataFrame(cases_data)
        df_cases["created_date"] = pd.to_datetime(df_cases["created_date"], errors="coerce")
        
        # Filter Controls
        with st.expander("🔍 Filter Cases", expanded=False):
            fc1, fc2, fc3, fc4 = st.columns(4)
            with fc1:
                min_date = df_cases["created_date"].min()
                safe_min = min_date.date() if pd.notna(min_date) else pd.Timestamp.today().date()
                date_from = st.date_input("From Date", value=safe_min, key="filter_date_from")
            with fc2:
                max_date = df_cases["created_date"].max()
                safe_max = max_date.date() if pd.notna(max_date) else pd.Timestamp.today().date()
                date_to = st.date_input("To Date", value=safe_max, key="filter_date_to")
            with fc3:
                status_opts = ["All"] + sorted(df_cases["review_status"].unique().tolist())
                status_filter = st.selectbox("Status", status_opts, key="filter_status")
            with fc4:
                type_opts = ["All"] + sorted(df_cases["task_type"].dropna().unique().tolist())
                type_filter = st.selectbox("Report Type", type_opts, key="filter_type")

        # Apply filtration masks
        mask = (df_cases["created_date"].dt.date >= date_from) & (df_cases["created_date"].dt.date <= date_to)
        if status_filter != "All":
            mask &= (df_cases["review_status"] == status_filter)
        if type_filter != "All":
            mask &= (df_cases["task_type"] == type_filter)
        
        df_filtered = df_cases[mask].copy()
        df_filtered["created_date"] = df_filtered["created_date"].dt.strftime("%Y-%m-%d %H:%M")
        
        cols_to_show = [
            'case_id', 'created_date', 'source', 'review_status', 
            'extraction_status', 'task_type', 'filename'
        ]
        df_filtered = df_filtered[cols_to_show]
        df_filtered.columns = [
            "Case ID", "Created Date", "Source", "Review Status", 
            "Extraction Status", "Report Type", "File Name"
        ]

        st.caption(f"Showing {len(df_filtered)} of {len(df_cases)} cases")
        st.dataframe(
            df_filtered,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    
    # --- Stalled Case Management ---
    pending_cases = [
        c for c in cases_data 
        if "Pending Review" in c["review_status"] or "Error" in c["review_status"]
    ]
    
    if pending_cases:
        st.subheader("🛠️ Manage Stalled Cases")
        st.markdown("Resume or remove datasets that may have been interrupted by service restarts.")
        
        case_lookup = {c['case_id']: c for c in pending_cases}
        case_mapping = {f"{c['filename']} (ID: {c['case_id']})": c['case_id'] for c in pending_cases}
        selected_case_label = st.selectbox("Select Case to Manage", list(case_mapping.keys()))

        selected_case_id = case_mapping[selected_case_label]
        selected_status = case_lookup[selected_case_id]["review_status"]
        
        if "Error" in selected_status:
            st.error(f"**Reason for failure:** {selected_status}")
        else:
            st.warning(f"**Status:** {selected_status} — Processing may have stalled.")

        col_act1, col_act2 = st.columns([1, 4])
        with col_act1:
            if st.button("🔄 Retry Processing", use_container_width=True):
                try:
                    retry_res = requests.post(f"{API_URL}/ingest/cases/{selected_case_id}/retry", timeout=5)
                    if retry_res.status_code == 200:
                        st.success("Task added back to queue!")
                        st.rerun()
                    else:
                        st.error(f"Server error: {retry_res.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")
        with col_act2:
            if st.button("🗑️ Delete Case"):
                try:
                    del_res = requests.delete(f"{API_URL}/ingest/cases/{selected_case_id}", timeout=5)
                    if del_res.status_code == 200:
                        st.success("Case successfully deleted.")
                        st.rerun()
                    else:
                        st.error(f"Server error: {del_res.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

