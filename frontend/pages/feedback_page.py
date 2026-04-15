import base64
import io
import requests
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from streamlit_autorefresh import st_autorefresh
from analytics_dashboard.charts import (
    generate_sentiment_bar_chart,
    generate_sentiment_line_chart,
    generate_sentiment_pie_chart,
    generate_keyword_frequency_chart
)
from analytics_dashboard.data_loader import aggregate_user_data
from frontend.utils.export_utils import export_to_format

import os
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def fetch_report_data(case_id, page=1, limit=10, search="", sentiment=None, sort_by=None, sort_order="desc"):
    try:
        res = requests.get(
            f"{API_URL}/ingest/results/{case_id}",
            params={
                "page": page, 
                "limit": limit, 
                "search": search,
                "sentiment": sentiment,
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            headers=get_headers(),
            timeout=10
        )
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def get_cached_aggregation(df):
    """Aggregates user-level data from enriched dataframe."""
    try:
        agg = aggregate_user_data(df)
        if agg is not None:
            id_cols = [c for c in agg.columns if any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
            if id_cols:
                agg['_search_id'] = agg[id_cols[0]].astype(str).str.lower()
        return agg
    except Exception:
        return None

def get_processed_results(data_results):
    """Processes a single page of results for display."""
    if not data_results: return pd.DataFrame()
    df = pd.DataFrame(data_results)
    if 'label' in df.columns:
         df.rename(columns={'label': 'sentiment_label'}, inplace=True)
    if 'review' in df.columns:
         df.rename(columns={'review': 'feedback_text'}, inplace=True)
    # Normalize score column name (data_upload pipeline uses 'sentiment_score', ingest uses 'score')
    if 'sentiment_score' in df.columns and 'score' not in df.columns:
         df.rename(columns={'sentiment_score': 'score'}, inplace=True)
    return df

def get_processed_enriched(csv_b64):
    """Caches enriched CSV parsing."""
    if not csv_b64: return None
    try:
        csv_bytes = base64.b64decode(csv_b64)
        df = pd.read_csv(io.BytesIO(csv_bytes))
        # Ensure searching works on enriched as well
        id_cols = [c for c in df.columns if any(k in c.lower() for k in ["userid", "user_id", "customerid", "customer_id", "id"])]
        if id_cols:
            df['_search_id'] = df[id_cols[0]].astype(str).str.lower()
        return normalize_dataframe_columns(df)
    except Exception:
        return None

def show():
    """
    Main entry point for the Sentiment Analysis report page. 
    Synchronized with live results via 5s polling.
    """
    # Silent 5s heartbeat to catch new background report completions
    # st_autorefresh(interval=5000, key="report_page_live_sync")
    
    st.title("💬 Sentiment Analysis")
    st.markdown("Select an ingested dataset to view the sentiment analysis report.")
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

    sentiment_cases = sorted([
        c for c in cases_data 
        if c.get("task_type") == "Sentiment Analysis" and str(c.get("review_status")).lower() == "completed"
    ], key=lambda x: x.get("id", 0), reverse=True)

    if not sentiment_cases:
        st.info(
            "No completed Sentiment Analysis datasets found. "
            "Go to 'Document Ingestion' to start an analysis."
        )
        return

    # Map labels to case IDs (Maintaining NEWEST FIRST order)
    case_mapping = {
        f"🆕 {c['filename']} (ID: {c['case_id']})" if i == 0 else f"{c['filename']} (ID: {c['case_id']})": c['case_id'] 
        for i, c in enumerate(sentiment_cases)
    }
    
    selected_case_label = st.selectbox(
        "Select Dataset", 
        list(case_mapping.keys()), 
        key="select_sentiment_dataset"
    )
    if st.button("📊 View Report", width='stretch', key="btn_view_sentiment"):
        # Clear previous search when viewing a new report
        if "feedback_search_query" in st.session_state:
            st.session_state.feedback_search_query = ""
            
        case_id = case_mapping[selected_case_label]
        # Silently check if we already have this case loaded to avoid re-fetching
        if st.session_state.get("active_feedback_case_id") == case_id and st.session_state.get("analysis_results"):
             pass # Already loaded
        else:
            with st.status("Analyzing sentiment patterns...", expanded=False):
                try:
                    res = requests.get(f"{API_URL}/ingest/results/{case_id}", headers=get_headers(), timeout=30)
                    if res.status_code == 200:
                        results_data = res.json()
                        st.session_state.analysis_results = results_data
                        st.session_state.active_feedback_case_id = case_id
                        
                        # --- Optimized Pre-processing (Using new features) ---
                        st.session_state.processed_results_df = get_processed_results(results_data.get("results", []))
                        
                        df_enriched = get_processed_enriched(results_data.get("enriched_csv"))

                        st.session_state.processed_enriched_df = df_enriched
                        
                        # SPEED OPTIMIZATION: Prioritize backend pre-computed data
                        user_agg_raw = results_data.get("user_engagement", [])
                        if user_agg_raw:
                            agg_df = pd.DataFrame(user_agg_raw)
                            # Create search index for ID columns
                            id_cols = [c for c in agg_df.columns if any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
                            if id_cols:
                                agg_df['_search_id'] = agg_df[id_cols[0]].astype(str).str.lower()
                            st.session_state.processed_agg_df = agg_df
                        elif df_enriched is not None:
                            # Only compute if backend failed to provide it
                            st.session_state.processed_agg_df = get_cached_aggregation(df_enriched)
                        else:
                            st.session_state.processed_agg_df = None
                    else:
                        st.error(f"Error fetching results: {res.text}")
                except Exception as e:
                    st.error(f"Processing error: {e}")


    if "analysis_results" in st.session_state:
        # Self-healing data restoration
        df_enriched = st.session_state.get("processed_enriched_df")
        agg_df = st.session_state.get("processed_agg_df")
        
        if agg_df is None and df_enriched is not None:
            # Recompute it safely if it got dropped from session_state
            agg_df = get_cached_aggregation(df_enriched)
            if agg_df is not None:
                st.session_state.processed_agg_df = agg_df
                
        show_results(
            st.session_state.analysis_results,
            st.session_state.get("processed_results_df"),
            df_enriched,
            agg_df,
            st.session_state.get("active_feedback_case_id")
        )


def show_results(data, results_df, df_enriched, agg_df, case_id):

    """Renders reports using server-side pagination."""
    st.subheader("📊 Key Performance Indicators")
    total = data['total']
    positive = data.get('positive', 0)
    negative = data.get('negative', 0)
    neutral = data.get('neutral', 0)
    
    pos_pct = (positive / total * 100) if total > 0 else 0
    neg_pct = (negative / total * 100) if total > 0 else 0
    neu_pct = (neutral / total * 100) if total > 0 else 0
    nss = pos_pct - neg_pct
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Reviews", total)
    m2.metric("Positive", f"{pos_pct:.1f}%")
    m3.metric("Neutral", f"{neu_pct:.1f}%")
    m4.metric("Negative", f"{neg_pct:.1f}%")
    
    if total < 30:
        m5.metric("Net Sentiment (NSS)", "N/A")
        st.caption("⚠️ **Sample size too small (<30)** for reliable NSS calculation.")
    else:
        m5.metric("Net Sentiment (NSS)", f"{nss:+.1f}")
    
    st.divider()
    
    # --- Visualizations Pipeline ---
    df_to_plot = df_enriched if df_enriched is not None else results_df
    render_visualizations_fragment(data, df_to_plot) 
    
    # --- User-Level Aggregation ---
    render_user_aggregation_fragment_v2(agg_df)

    render_keyword_tabs(data)
    st.divider()

    # --- Detailed Results Table ---
    render_results_table_v2(results_df, case_id)


@st.fragment
def render_user_aggregation_fragment_v2(agg_df_all):
    """
    Renders user-level statistics with high-density styling, filtering, and pagination.
    """
    st.subheader("👤 Per-User Intelligence")
    
    # Handle the case where aggregation data is completely missing
    if agg_df_all is None:
        st.info("No user-level data available. (Dataframe is None - please click 'View Report' again).")
        st.divider()
        return
        
    if hasattr(agg_df_all, 'empty') and agg_df_all.empty:
        st.info(f"No user-level data available. Your dataset may not contain a recognized user/customer ID column. Found columns: {list(agg_df_all.columns)}")
        st.divider()
        return
    
    # Define clear callback for search reset
    def clear_agg_search():
        st.session_state.agg_q_in = ""

    # --- Filters Row ---
    with st.container(border=True):
        c_in, c_filter, c_search, c_clear = st.columns([3, 1.5, 1, 1])
        with c_in:
            agg_query = st.text_input("Search ID", key="agg_q_in", label_visibility="collapsed", placeholder="🔍 Search by Customer ID...")
        with c_filter:
            # Dynamic filter: detect dominant sentiment column
            sentiment_col = next((c for c in agg_df_all.columns if 'dominant' in c.lower() or 'sentiment summary' in c.lower()), None)
            if sentiment_col:
                unique_sentiments = sorted(agg_df_all[sentiment_col].dropna().unique().tolist())
                filter_opts = ["All Sentiments"] + unique_sentiments
                agg_sentiment_filter = st.selectbox(
                    "Filter Sentiment", filter_opts, 
                    key="agg_sentiment_filter", label_visibility="collapsed"
                )
            else:
                agg_sentiment_filter = "All Sentiments"
        with c_search:
            st.button("🔍 Search", use_container_width=True, key="btn_agg_search")
        with c_clear:
            st.button("🗑️ Clear", use_container_width=True, key="btn_agg_clear", on_click=clear_agg_search)

    agg_df = agg_df_all.copy()
    
    # Apply ID search filter
    if agg_query and agg_query.strip():
        query_lower = agg_query.strip().lower()
        id_cols = [c for c in agg_df.columns if c != '_search_id' and any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
        if id_cols:
            agg_df = agg_df[agg_df[id_cols[0]].astype(str).str.lower().str.contains(query_lower, na=False)]
    
    # Apply sentiment filter
    if sentiment_col and agg_sentiment_filter != "All Sentiments":
        agg_df = agg_df[agg_df[sentiment_col] == agg_sentiment_filter]
    
    # Hide internal columns and deprecated fields from display
    _excluded = {'Total Comments', 'Total Feedback'}
    display_cols = [c for c in agg_df.columns if not c.startswith('_') and c not in _excluded]
    
    if not agg_df.empty:
        items_per_page = 10
        total_items = len(agg_df)
        total_pages = (total_items - 1) // items_per_page + 1
        
        if "user_agg_page" not in st.session_state: st.session_state.user_agg_page = 1
        st.session_state.user_agg_page = min(st.session_state.user_agg_page, total_pages)
            
        start_idx = (st.session_state.user_agg_page - 1) * items_per_page
        df_page = agg_df[display_cols].iloc[start_idx : start_idx + items_per_page]
        
        st.dataframe(df_page, use_container_width=True, hide_index=True)
        
        # Compact Pagination
        pa1, pa2, pa3 = st.columns([1, 2, 1])
        with pa1:
            if st.button("⬅️", disabled=st.session_state.user_agg_page <= 1, key="ua_prev"):
                st.session_state.user_agg_page -= 1; st.rerun()
        with pa3:
            if st.button("➡️", disabled=st.session_state.user_agg_page >= total_pages, key="ua_next"):
                st.session_state.user_agg_page += 1; st.rerun()
        with pa2:
            st.markdown(f"<p style='text-align:center; font-size:0.85rem;'>{st.session_state.user_agg_page} / {total_pages}</p>", unsafe_allow_html=True)
    else:
        st.warning("No records match your filters. Try a different Customer ID or sentiment.")
    st.divider()

def normalize_dataframe_columns(df):
    """
    Normalizes column names for consistent downstream processing.
    """
    # Map sentiment dynamically
    sentiment_col = next(
        (c for c in df.columns if c.lower() in ['sentimentlabel', 'sentiment_label', 'label', 'sentiment']), 
        None
    )
    if not sentiment_col:
        sentiment_col = next(
            (c for c in df.columns if 'sentiment' in c.lower() or 'label' in c.lower()), 
            None
        )
    if sentiment_col:
        # Use loc to avoid SettingWithCopyWarning
        df.rename(columns={sentiment_col: 'sentiment_label'}, inplace=True)

    # Map Text dynamically
    text_col = next(
        (c for c in df.columns if c.lower() in ['review', 'feedback', 'text', 'comment', 'feedback_text']), 
        None
    )
    if not text_col:
        text_col = next(
            (c for c in df.columns if 'review' in c.lower() or 'feedback' in c.lower()), 
            None
        )
    if text_col:
        # Use loc to avoid SettingWithCopyWarning
        df.rename(columns={text_col: 'feedback_text'}, inplace=True)
    return df

@st.fragment
def render_visualizations_fragment(data, df_to_plot):
    """
    Renders selected or all charts in an isolated fragment for high-speed switching.
    """
    render_visualizations(data, df_to_plot)

def render_visualizations(data, df_to_plot):
    """
    Renders selected or all charts for the sentiment dataset.
    Uses global counts for summary charts to ensure 100% accuracy.
    """
    st.subheader("📈 Visual Insights")
    
    # 1. Prepare data sources
    # Global counts for summary charts
    global_counts = {
        "POSITIVE": data.get("positive", 0),
        "NEGATIVE": data.get("negative", 0),
        "NEUTRAL": data.get("neutral", 0)
    }
    
    chart_opts = [
        "All Visualizations (Grid)", 
        "Sentiment Distribution (Bar)", 
        "Sentiment Share (Pie)",
        "Sentiment Over Time (Trends)",
        "Top Keywords (Chart)"
    ]
    selected_chart = st.selectbox("Select Chart View", chart_opts, key="viz_selector")
    
    if selected_chart == "All Visualizations (Grid)":
        c1, c2 = st.columns(2)
        with c1:
            generate_sentiment_bar_chart(counts_dict=global_counts)
            generate_sentiment_line_chart(df_to_plot)
        with c2:
            generate_sentiment_pie_chart(counts_dict=global_counts)
            # Transform keyword data for chart
            freq_data = [(k["word"], k["count"]) for k in data.get("freq_keywords", [])]
            generate_keyword_frequency_chart(freq_data)
                
    elif selected_chart == "Sentiment Distribution (Bar)":
        generate_sentiment_bar_chart(counts_dict=global_counts)
    elif selected_chart == "Sentiment Share (Pie)":
        generate_sentiment_pie_chart(counts_dict=global_counts)
    elif selected_chart == "Sentiment Over Time (Trends)":
        generate_sentiment_line_chart(df_to_plot)
    elif selected_chart == "Top Keywords (Chart)":
        freq_data = [(k["word"], k["count"]) for k in data.get("freq_keywords", [])]
        generate_keyword_frequency_chart(freq_data)

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
                st.rerun()
        with c2:
            st.markdown(f"<p style='text-align:center'>Page {st.session_state.user_agg_page_idx} of {total_pages}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("Next ➡️", disabled=st.session_state.user_agg_page_idx >= total_pages, key="up_next", width="stretch"):
                st.session_state.user_agg_page_idx += 1
                st.rerun()

    _user_agg_fragment()

def render_results_table_v2(results_df, case_id):
    """Renders the detailed results table with local-first pagination, filtering, and sorting."""
    @st.fragment
    def _results_fragment():
        st.subheader("📋 Detailed Feedback Review")
        
        # Initialize page state
        if "feedback_page_num" not in st.session_state: st.session_state.feedback_page_num = 1

        # --- Filters Row (Using widget keys directly - no dual-state) ---
        with st.container(border=True):
            f1, f2 = st.columns([3, 1])
            with f1:
                search_query = st.text_input(
                    "🔍 Search", 
                    placeholder="Search reviews...", 
                    label_visibility="collapsed",
                    key="dfr_search_input"
                )
            with f2:
                filter_options = ["All", "Positive", "Neutral", "Negative"]
                sentiment_filter = st.selectbox(
                    "Sentiment Filter", 
                    filter_options, 
                    label_visibility="collapsed",
                    key="dfr_sentiment_select"
                )

        # Reset page to 1 when filters change
        filter_sig = f"{search_query}|{sentiment_filter}"
        if st.session_state.get("_dfr_filter_sig") != filter_sig:
            st.session_state._dfr_filter_sig = filter_sig
            st.session_state.feedback_page_num = 1

        page = st.session_state.get("feedback_page_num", 1)
        data = fetch_report_data(
            case_id, 
            page=page, 
            limit=10, 
            search=search_query,
            sentiment=sentiment_filter if sentiment_filter != "All" else None,
            sort_by=None,
            sort_order="desc"
        )
            
        if not data or "results" not in data or not data["results"]:
            st.warning("No results found matching your criteria.")
            return

        df_page = get_processed_results(data["results"])
        
        # --- Column Cleanup for Display ---
        # 1. Identify valid columns
        valid_cols = []
        # Priority columns — feedback, sentiment label, and score
        priority = ['feedback_text', 'sentiment_label', 'score']
        for p in priority:
            if p in df_page.columns: valid_cols.append(p)
            
        # Add relevant secondary columns (IDs, product info, dates)
        for c in df_page.columns:
            if c in valid_cols: continue
            c_low = c.lower()
            # Technical black-list (internal/noise columns)
            if any(x in c_low for x in ['numerator', 'denominator', 'feature', 'unnamed', '_search']):
                continue
            # Keep user IDs, product IDs, and date columns
            if any(x in c_low for x in ['userid', 'user_id', 'customer', 'productid', 'product_id', 'id', 'date', 'time']):
                valid_cols.append(c)
        
        df_display = df_page[valid_cols].copy() if valid_cols else df_page.copy()
        
        # 2. Pretty Renaming
        rename_map = {
            'feedback_text': 'Feedback',
            'sentiment_label': 'Sentiment',
            'score': 'Sentiment Score'
        }
        df_display.rename(columns=rename_map, inplace=True)
        
        # 3. Ensure Sentiment Score column is present (fallback)
        if 'Sentiment Score' not in df_display.columns:
            # Check alternate column names
            for alt in ['score', 'sentiment_score']:
                if alt in df_page.columns:
                    df_display['Sentiment Score'] = df_page[alt]
                    break

        # Display clean dataframe
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)

        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️ Prev", disabled=page <= 1, width="stretch", key="fb_prev"):
                st.session_state.feedback_page_num -= 1
                st.rerun()
        with c2:
            st.markdown(f"<p style='text-align:center'>Page {page} of {total_pages}</p>", unsafe_allow_html=True)
        with c3:
            if st.button("Next ➡️", disabled=page >= total_pages, width="stretch", key="fb_next"):
                st.session_state.feedback_page_num += 1
                st.rerun()
    
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
            df_tfidf = pd.DataFrame(tfidf_kw)
            if "count" in df_tfidf.columns and "score" not in df_tfidf.columns:
                df_tfidf.rename(columns={"count": "score"}, inplace=True)
            
            # Ensure both required columns exist before filtering
            available_cols = [c for c in ["word", "score"] if c in df_tfidf.columns]
            st.dataframe(df_tfidf[available_cols], use_container_width=True, hide_index=True)
