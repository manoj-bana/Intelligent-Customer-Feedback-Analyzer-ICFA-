import base64
import io
import requests
import streamlit as st
import pandas as pd
from analytics_dashboard.charts import (
    generate_sentiment_bar_chart,
    generate_sentiment_line_chart,
    generate_sentiment_pie_chart,
    generate_keyword_frequency_chart
)
from frontend.utils.export_utils import export_to_format

API_URL = "http://127.0.0.1:8000"

@st.cache_data(ttl=300)
def fetch_report_data(case_id, page=1, limit=10, search=""):
    """Fetches a specific page of results from the backend."""
    try:
        params = {"page": page, "limit": limit, "search": search}
        res = requests.get(f"{API_URL}/ingest/results/{case_id}", params=params, timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Error fetching page {page}: {e}")
    return None

def get_processed_results(data_results):
    """Processes a single page of results for display."""
    if not data_results: return pd.DataFrame()
    df = pd.DataFrame(data_results)
    if 'label' in df.columns:
         df.rename(columns={'label': 'sentiment_label'}, inplace=True)
    if 'review' in df.columns:
         df.rename(columns={'review': 'feedback_text'}, inplace=True)
    return df

def show():
    """Main entry point for the Sentiment Analysis report page."""
    st.title("💬 Sentiment Analysis")
    st.markdown("Select an ingested dataset to view the sentiment analysis report.")
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

    sentiment_cases = [
        c for c in cases_data 
        if c.get("task_type") == "Sentiment Analysis" and c.get("review_status") == "Completed"
    ]

    if not sentiment_cases:
        st.info("No completed Sentiment Analysis datasets found.")
        return

    case_mapping = {f"{c['filename']} (ID: {c['case_id']})": c['case_id'] for c in sentiment_cases}
    selected_case_label = st.selectbox("Select Dataset", list(case_mapping.keys()), key="select_sentiment_dataset")
    
    if st.button("📊 View Report", width='stretch', key="btn_view_sentiment") or st.session_state.get("active_case_id") == case_mapping[selected_case_label]:
        case_id = case_mapping[selected_case_label]
        
        if st.session_state.get("active_case_id") != case_id:
            st.session_state.active_case_id = case_id
            st.session_state.feedback_page_num = 1
            st.session_state.res_q_in = ""
            st.session_state.analysis_metadata = None

        if st.session_state.analysis_metadata is None:
            with st.spinner("Fetching report summary..."):
                # Fetch first page to get metadata/KPIs and the 10k row results preview
                data = fetch_report_data(case_id, page=1, limit=10000) 
                if data:
                    st.session_state.analysis_metadata = data

        if st.session_state.analysis_metadata:
            show_results(st.session_state.active_case_id, st.session_state.analysis_metadata)

def show_results(case_id, metadata):
    """Renders reports using server-side pagination."""
    st.subheader("📊 Key Performance Indicators")
    total = metadata['total']
    pos_pct = (metadata['positive'] / total * 100) if total > 0 else 0
    neg_pct = (metadata['negative'] / total * 100) if total > 0 else 0
    nss = pos_pct - neg_pct
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Reviews", total)
    m2.metric("Positive", f"{pos_pct:.1f}%")
    m3.metric("Negative", f"{neg_pct:.1f}%")
    m4.metric("Net Sentiment (NSS)", f"{nss:+.1f}")
    
    st.divider()

    # --- Visualizations ---
    if "results" in metadata and metadata["results"]:
        render_visualizations(metadata)

    # --- Per-User Aggregation ---
    if "user_engagement" in metadata:
        render_user_aggregation_backend(metadata["user_engagement"])

    render_keyword_tabs(metadata)
    st.divider()
    render_results_table_paginated(case_id)

def render_visualizations(metadata):
    """Renders charts using the results preview data."""
    st.subheader("📈 Visual Insights")
    
    # Convert results preview to temporary DataFrame for plotting
    df_plot = pd.DataFrame(metadata["results"])
    if 'label' in df_plot.columns:
         df_plot.rename(columns={'label': 'sentiment_label'}, inplace=True)
    
    chart_opts = [
        "All Visualizations (Grid)", 
        "Sentiment Distribution (Bar)", 
        "Sentiment Share (Pie)"
    ]
    selected_chart = st.selectbox("Select Chart View", chart_opts, key="viz_selector")
    
    if selected_chart == "All Visualizations (Grid)":
        c1, c2 = st.columns(2)
        with c1:
            generate_sentiment_bar_chart(df_plot)
        with c2:
            generate_sentiment_pie_chart(df_plot)
                
    elif selected_chart == "Sentiment Distribution (Bar)":
        generate_sentiment_bar_chart(df_plot)
    elif selected_chart == "Sentiment Share (Pie)":
        generate_sentiment_pie_chart(df_plot)

def render_user_aggregation_backend(user_engagement):
    """
    Renders the pre-aggregated user list from backend with pagination.
    Uses @st.fragment to ensure pagination is instant and doesn't reload the report.
    """
    @st.fragment
    def _user_agg_fragment():
        st.subheader("👤 Per-User Analysis (Aggregated)")
        if not user_engagement:
            st.info("No user-level data available.")
            return

        df_user_full = pd.DataFrame(user_engagement)
        
        # Search for specific User ID
        search_uid = st.text_input("🔍 Search User ID", placeholder="Enter ID...", key="user_id_search")
        if search_uid:
            # Find the ID column
            uid_col = next((c for c in df_user_full.columns if any(k in c.lower() for k in ["userid", "user id", "id"])), df_user_full.columns[0])
            df_user_display = df_user_full[df_user_full[uid_col].astype(str).str.contains(search_uid.strip(), case=False)]
        else:
            df_user_display = df_user_full

        # Pagination Logic
        items_per_page = 10
        total_items = len(df_user_display)
        total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
        
        # Track page in session state for this specific fragment
        if "user_agg_page_idx" not in st.session_state:
            st.session_state.user_agg_page_idx = 1
        
        # Reset if search changes the total pages significantly
        if st.session_state.user_agg_page_idx > total_pages:
            st.session_state.user_agg_page_idx = total_pages

        # Render Table
        start_idx = (st.session_state.user_agg_page_idx - 1) * items_per_page
        end_idx = start_idx + items_per_page
        st.dataframe(df_user_display.iloc[start_idx:end_idx], use_container_width=True, hide_index=True)

        # Pagination Controls
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️ Prev", disabled=st.session_state.user_agg_page_idx <= 1, key="up_prev", width="stretch"):
                st.session_state.user_agg_page_idx -= 1
                st.rerun(scope="fragment")
        with c2:
            st.markdown(f"<p style='text-align:center'>Page {st.session_state.user_agg_page_idx} of {total_pages}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("Next ➡️", disabled=st.session_state.user_agg_page_idx >= total_pages, key="up_next", width="stretch"):
                st.session_state.user_agg_page_idx += 1
                st.rerun(scope="fragment")

    _user_agg_fragment()

def render_results_table_paginated(case_id):
    """Renders the detailed results table with server-side pagination."""
    @st.fragment
    def _results_fragment():
        st.subheader("📋 Detailed Feedback Review")
        
        search_query = st.text_input("🔍 Search Reviews", value=st.session_state.get("res_q_in", ""), placeholder="Type to filter...")
        if search_query != st.session_state.get("res_q_in"):
            st.session_state.res_q_in = search_query
            st.session_state.feedback_page_num = 1
            st.rerun(scope="fragment")

        page = st.session_state.get("feedback_page_num", 1)
        data = fetch_report_data(case_id, page=page, limit=10, search=search_query)
            
        if not data or "results" not in data or not data["results"]:
            st.warning("No results found.")
            return

        df_page = get_processed_results(data["results"])
        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)

        st.dataframe(df_page, use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️ Prev", disabled=page <= 1, width="stretch", key="fb_prev"):
                st.session_state.feedback_page_num -= 1
                st.rerun(scope="fragment")
        with c2:
            st.markdown(f"<p style='text-align:center'>Page {page} of {total_pages}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("Next ➡️", disabled=page >= total_pages, width="stretch", key="fb_next"):
                st.session_state.feedback_page_num += 1
                st.rerun(scope="fragment")
    
    _results_fragment()

def render_keyword_tabs(data):
    """Renders keyword themes."""
    st.subheader("🔑 Voice of the Customer (Themes)")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Top Mentioned Topics**")
        freq_kw = data.get("freq_keywords", [])
        if freq_kw:
            st.dataframe(pd.DataFrame(freq_kw)[["word", "count"]], use_container_width=True, hide_index=True)
    with col2:
        st.write("**Unique Sentiment Drivers**")
        tfidf_kw = data.get("tfidf_keywords", [])
        if tfidf_kw:
            st.dataframe(pd.DataFrame(tfidf_kw)[["word", "score"]], use_container_width=True, hide_index=True)
