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

    # Handle page persistence in query params
    pages = ["🏠 Home", "☁️ Document Ingestion", "📊 Reports"]
    query_page = st.query_params.get("page", "🏠 Home")
    page_index = 0
    if query_page in pages:
        page_index = pages.index(query_page)

    page = st.sidebar.radio(
        "Navigate",
        pages,
        index=page_index
    )
    
    # Update query params to current page if it changed
    if st.query_params.get("page") != page:
        st.query_params["page"] = page

    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.token = ""
        
        # Clear query params to prevent auto-login on refresh
        st.query_params.clear()
        
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

@st.cache_data(ttl=60) # Cache for 60 seconds to allow for new uploads
def get_cases(username):
    """
    Fetches analysis cases from the backend. 
    Cached to prevent redundant API calls during pagination.
    """
    try:
        res = requests.get(f"{API_URL}/ingest/cases/{username}", timeout=10)
        if res.status_code == 200:
            return res.json().get("cases", [])
    except Exception:
        pass
    return []

def show_home():
    """
    Renders the Home page of the dashboard with global KPIs and a data grid of user cases.
    """
    st.title("📊 ICFA Dashboard")
    st.markdown("### Intelligent Customer Feedback Analyzer")
    st.divider()

    username = st.session_state.get("username", "")

    # --- Data Fetching ---
    cases_data = get_cases(username)

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
    render_cases_fragment(cases_data)

@st.fragment
def render_cases_fragment(cases_data):
    """
    Renders the cases list in an isolated fragment for high-speed pagination.
    Only this block reruns when navigating between pages.
    """
    st.subheader("My Cases")
    
    if not cases_data:
        st.info("No cases found. Navigate to `Document Ingestion` to upload your first dataset!")
        return

    df_cases = pd.DataFrame(cases_data)
    df_cases["created_date"] = pd.to_datetime(df_cases["created_date"], errors="coerce")
    
    # Reset pagination if filters change
    def reset_page():
        st.session_state.current_page = 1

    # Filter Controls
    with st.expander("🔍 Filter Cases", expanded=False):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            min_date = df_cases["created_date"].min()
            safe_min = min_date.date() if pd.notna(min_date) else pd.Timestamp.today().date()
            date_from = st.date_input("From Date", value=safe_min, key="filter_date_from", on_change=reset_page)
        with fc2:
            max_date = df_cases["created_date"].max()
            safe_max = max_date.date() if pd.notna(max_date) else pd.Timestamp.today().date()
            date_to = st.date_input("To Date", value=safe_max, key="filter_date_to", on_change=reset_page)
        with fc3:
            status_opts = ["All"] + sorted(df_cases["review_status"].unique().tolist())
            status_filter = st.selectbox("Status", status_opts, key="filter_status", on_change=reset_page)
        with fc4:
            type_opts = ["All"] + sorted(df_cases["task_type"].dropna().unique().tolist())
            type_filter = st.selectbox("Report Type", type_opts, key="filter_type", on_change=reset_page)

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

    # --- Pagination Logic ---
    items_per_page = 10
    total_items = len(df_filtered)
    total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
    
    if "current_page" not in st.session_state:
        st.session_state.current_page = 1
        
    # Clamp current page to valid range
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = total_pages
    if st.session_state.current_page < 1:
        st.session_state.current_page = 1

    # Pagination Controls (at the top)
    pg_col1, pg_col2, pg_col3, pg_col4 = st.columns([2, 3, 2, 2])
    
    # Check for interactions before slicing
    with pg_col1:
        if st.button("⬅️ Previous", disabled=st.session_state.current_page <= 1, width='stretch'):
            st.session_state.current_page -= 1
            try: st.rerun(scope="fragment")
            except: st.rerun()
            
    with pg_col2:
        # Placeholder
        pass
        
    with pg_col3:
        if st.button("Next ➡️", disabled=st.session_state.current_page >= total_pages, width='stretch'):
            st.session_state.current_page += 1
            try: st.rerun(scope="fragment")
            except: st.rerun()
    
    with pg_col4:
        # Jump to page selector
        if total_pages > 1:
            jump_page = st.selectbox(
                "Jump to", 
                range(1, total_pages + 1), 
                index=max(0, st.session_state.current_page - 1),
                label_visibility="collapsed",
                key="dash_jump_page"
            )
            if jump_page != st.session_state.current_page:
                st.session_state.current_page = jump_page
                try: st.rerun(scope="fragment")
                except: st.rerun()

    # Slice Data Calculation
    start_idx = (st.session_state.current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page

    with pg_col2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 5px; font-size: 1.1rem;'>"
            f"Page <b>{st.session_state.current_page}</b> of <b>{total_pages}</b>"
            f"</div>", 
            unsafe_allow_html=True
        )

    st.caption(f"Showing items {start_idx + 1} to {min(end_idx, total_items)} of {total_items}")

    # Slice Data
    df_page = df_filtered.iloc[start_idx:end_idx]

    st.dataframe(
        df_page,
        width='stretch',
        hide_index=True,
    )

    st.divider()
    
    # --- Dataset Management ---
    if cases_data:
        st.subheader("🗑️ Manage & Delete Datasets")
        st.markdown("Select a dataset below to delete it from the system or retry stalled processing.")
        
        # All cases are now manageable
        case_lookup = {c['case_id']: c for c in cases_data}
        case_mapping = {f"{c['filename']} (ID: {c['case_id']}, Status: {c['review_status']})": c['case_id'] for c in cases_data}
        
        selected_case_label = st.selectbox("Select Dataset to Manage", list(case_mapping.keys()), key="manage_case_selector")
        selected_case_id = case_mapping[selected_case_label]
        selected_case = case_lookup[selected_case_id]
        
        col_act1, col_act2 = st.columns([1, 4])
        with col_act1:
            # Only show Retry button for stalled/error cases
            if "Completed" not in selected_case["review_status"]:
                if st.button("🔄 Retry", width='stretch', key="btn_retry_case"):
                    try:
                        retry_res = requests.post(f"{API_URL}/ingest/cases/{selected_case_id}/retry", timeout=5)
                        if retry_res.status_code == 200:
                            st.success("Task added back to queue!")
                            st.rerun()
                        else:
                            st.error(f"Server error: {retry_res.text}")
                    except Exception as e:
                        st.error(f"Connection error: {e}")
            else:
                st.info("Analysis Complete")
                
        with col_act2:
            if st.button("🗑️ Delete Dataset", key="btn_delete_case"):
                try:
                    del_res = requests.delete(f"{API_URL}/ingest/cases/{selected_case_id}", timeout=5)
                    if del_res.status_code == 200:
                        st.success("Dataset successfully deleted.")
                        st.rerun()
                    else:
                        st.error(f"Server error: {del_res.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

