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

API_URL = "http://127.0.0.1:8000"

def get_cached_aggregation(df):
    """Aggregates user-level data from enriched dataframe."""
    try:
        print(f"[DEBUG] get_cached_aggregation called. df columns: {list(df.columns)[:8]}")
        print(f"[DEBUG] df shape: {df.shape}")
        agg = aggregate_user_data(df)
        print(f"[DEBUG] aggregate_user_data returned: {type(agg)}, rows: {len(agg) if agg is not None else 'None'}")
        if agg is not None:
            id_cols = [c for c in agg.columns if any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
            if id_cols:
                agg['_search_id'] = agg[id_cols[0]].astype(str).str.lower()
        return agg
    except Exception as e:
        print(f"[ERROR] get_cached_aggregation failed: {e}")
        import traceback; traceback.print_exc()
        return None

def get_processed_results(data_results):
    """Caches results dataframe and pre-calculates a universal search index."""
    df = pd.DataFrame(data_results)
    if 'label' in df.columns:
         df.rename(columns={'label': 'sentiment_label'}, inplace=True)
    if 'review' in df.columns:
         df.rename(columns={'review': 'feedback_text'}, inplace=True)
    
    # Identify the ID column — match the same patterns as the backend
    # Exclude known non-ID columns to avoid false matches
    exclude_cols = {'score', 'sentiment_label', 'feedback_text', '_search_id', '_search_all'}
    id_cols = [c for c in df.columns if c not in exclude_cols and 
               any(k in c.lower() for k in ["userid", "user_id", "customerid", "customer_id", "id"])]
    if id_cols:
        df['_search_id'] = df[id_cols[0]].astype(str).str.strip().str.lower()
    return df

def get_processed_enriched(csv_b64):
    """Caches enriched CSV parsing."""
    if not csv_b64: return None
    try:
        csv_bytes = base64.b64decode(csv_b64)
        df = pd.read_csv(io.BytesIO(csv_bytes))
        print(f"[DEBUG] Enriched CSV parsed. Columns: {list(df.columns)}")
        # Ensure searching works on enriched as well
        id_cols = [c for c in df.columns if any(k in c.lower() for k in ["userid", "user_id", "customerid", "customer_id", "id"])]
        if id_cols:
            df['_search_id'] = df[id_cols[0]].astype(str).str.lower()
        return normalize_dataframe_columns(df)
    except Exception as e:
        print(f"[ERROR] get_processed_enriched failed: {e}")
        import traceback; traceback.print_exc()
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
        res = requests.get(f"{API_URL}/ingest/cases/{username}", timeout=10)
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
        with st.spinner("Preparing high-performance report data..."):
            try:
                res = requests.get(f"{API_URL}/ingest/results/{case_id}", timeout=30)
                if res.status_code == 200:
                    results_data = res.json()
                    st.session_state.analysis_results = results_data
                    
                    # --- Optimized Pre-processing (Using new features) ---
                    st.session_state.processed_results_df = get_processed_results(results_data.get("results", []))
                    
                    df_enriched = get_processed_enriched(results_data.get("enriched_csv"))
                    st.session_state.processed_enriched_df = df_enriched
                    
                    if df_enriched is not None:
                        st.session_state.processed_agg_df = get_cached_aggregation(df_enriched)
                    else:
                        # Fallback to backend pre-computed data if enrichment CSV is missing/large
                        user_agg_raw = results_data.get("user_engagement", [])
                        if user_agg_raw:
                            agg_fallback = pd.DataFrame(user_agg_raw)
                            # Ensure search index is still created for fallback data
                            id_cols = [c for c in agg_fallback.columns if any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
                            if id_cols:
                                agg_fallback['_search_id'] = agg_fallback[id_cols[0]].astype(str).str.lower()
                            st.session_state.processed_agg_df = agg_fallback
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
            agg_df
        )

def show_results(data, results_df, df_enriched, agg_df):
    """
    Renders optimized reports using pre-processed dataframes with search support.
    """
    st.subheader("📊 Key Performance Indicators")
    total = data['total']
    pos_pct = (data['positive'] / total * 100) if total > 0 else 0
    neg_pct = (data['negative'] / total * 100) if total > 0 else 0
    nss = pos_pct - neg_pct
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Reviews", total)
    m2.metric("Positive", f"{pos_pct:.1f}%", delta="Satisfaction", help="Percentage of total reviews evaluated as Positive.")
    m3.metric("Negative", f"{neg_pct:.1f}%", delta="-Pain Points", delta_color="inverse", help="Percentage of total reviews evaluated as Negative.")
    m4.metric("Net Sentiment (NSS)", f"{nss:+.1f}", delta="Health Score", delta_color="normal" if nss > 0 else "inverse", help="Net Sentiment Score: Positive % minus Negative %.")
    
    with st.expander("📝 Executive Summary & Insights", expanded=True):
        col_in1, col_in2 = st.columns([2, 1])
        with col_in1:
            if nss > 30:
                st.success(f"🌟 **Strong Performance:** The dataset shows a high NSS of {nss:.1f}. Customers are generally satisfied, particularly with keywords like: '{', '.join([k['word'] for k in data.get('freq_keywords', [])[:3]])}'.")
            elif nss < 0:
                st.error(f"⚠️ **Urgent Attention Needed:** The sentiment is leaning negative. Focus on resolving issues related to: '{', '.join([k['word'] for k in data.get('tfidf_keywords', [])[:3]])}'.")
            else:
                st.warning(f"⚖️ **Neutral Market Position:** Sentiment is balanced. There is a great opportunity to convert 'Neutral' users by focusing on missing features or service gaps.")
        with col_in2:
            st.button("📧 Email PDF Report", use_container_width=True, disabled=True)
            st.button("🔔 Set Alert for Negative spikes", use_container_width=True, disabled=True)

    st.divider()
    
    # --- Visualizations Pipeline ---
    df_to_plot = df_enriched if df_enriched is not None else results_df
    render_visualizations_fragment(data, df_to_plot)
    
    # --- User-Level Aggregation ---
    render_user_aggregation_fragment_v2(agg_df)

    # --- Keyword Discovery ---
    render_keyword_tabs(data)

    st.divider()

    # --- Detailed Results Table ---
    render_results_table_v2(results_df)

@st.fragment
def render_user_aggregation_fragment_v2(agg_df_all):
    """
    Renders user-level statistics with high-density styling and pagination.
    """
    st.subheader("👤 Per-User Intelligence")
    
    # Handle the case where aggregation data is completely missing
    # Handle the case where aggregation data is completely missing
    if agg_df_all is None:
        st.info("No user-level data available. (Dataframe is None - please click 'View Report' again).")
        st.divider()
        return
        
    if hasattr(agg_df_all, 'empty') and agg_df_all.empty:
        st.info(f"No user-level data available. Your dataset may not contain a recognized user/customer ID column. Found columns: {list(agg_df_all.columns)}")
        st.divider()
        return
    
    with st.container(border=True):
        c_in, c_search, c_clear = st.columns([3, 1, 1])
        with c_in:
            agg_query = st.text_input("Search ID", key="agg_q_in", label_visibility="collapsed", placeholder="Enter Customer ID...")
        with c_search:
            st.button("🔍 Search", use_container_width=True, key="btn_agg_search")
        with c_clear:
            if st.button("🗑️ Clear", use_container_width=True, key="btn_agg_clear"):
                st.session_state.agg_q_in = ""
                st.rerun(scope="fragment")

    agg_df = agg_df_all.copy()
    
    # Only filter when the user explicitly types a search query
    if agg_query and agg_query.strip():
        query_lower = agg_query.strip().lower()
        # Exclude internal columns from ID search
        id_cols = [c for c in agg_df.columns if c != '_search_id' and any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
        if id_cols:
            agg_df = agg_df[agg_df[id_cols[0]].astype(str).str.lower().str.contains(query_lower, na=False)]
    
    # Hide internal columns from display
    display_cols = [c for c in agg_df.columns if not c.startswith('_')]
    
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
                st.session_state.user_agg_page -= 1; st.rerun(scope="fragment")
        with pa3:
            if st.button("➡️", disabled=st.session_state.user_agg_page >= total_pages, key="ua_next"):
                st.session_state.user_agg_page += 1; st.rerun(scope="fragment")
        with pa2:
            st.markdown(f"<p style='text-align:center; font-size:0.85rem;'>{st.session_state.user_agg_page} / {total_pages}</p>", unsafe_allow_html=True)
    else:
        st.warning("No records match your search. Try a different Customer ID.")
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
    """
    st.subheader("📈 Visual Insights")
    
    chart_opts = [
        "All Visualizations (Grid)", 
        "Sentiment Distribution (Bar)", 
        "Sentiment Proportions (Pie)", 
        "Keyword Frequency Report", 
        "Sentiment Trend Analysis"
    ]
    selected_chart = st.selectbox("Select View", chart_opts, key="viz_selector")
    
    if selected_chart == "All Visualizations (Grid)":
        c1, c2, c3 = st.columns(3)
        with c1:
            generate_sentiment_bar_chart(df_to_plot)
        with c2:
            generate_sentiment_pie_chart(df_to_plot)
        with c3:
            render_freq_chart(data)
                
        st.write("")
        st.write("#### Sentiment Trend Analysis")
        generate_sentiment_line_chart(df_to_plot)
                
    elif selected_chart == "Sentiment Distribution (Bar)":
        generate_sentiment_bar_chart(df_to_plot)
    elif selected_chart == "Sentiment Proportions (Pie)":
        generate_sentiment_pie_chart(df_to_plot)
    elif selected_chart == "Keyword Frequency Report":
        render_freq_chart(data)
    elif selected_chart == "Sentiment Trend Analysis":
        generate_sentiment_line_chart(df_to_plot)

def render_freq_chart(data):
    """Helper to render frequency chart from results data."""
    freq_kw = data.get("freq_keywords") or data.get("keywords", [])
    if freq_kw:
        freq_for_charts = [(item["word"], item["count"]) for item in freq_kw[:10]]
        generate_keyword_frequency_chart(freq_for_charts)
    else:
        st.info("No frequency keywords available.")


def render_keyword_tabs(data):
    """
    Renders the keyword extraction. Consolidates redundant technical views into a clean layout.
    """
    st.subheader("🔑 Voice of the Customer (Themes)")
    
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        st.write("**Top Mentioned Topics**")
        freq_kw = data.get("freq_keywords") or data.get("keywords", [])
        if freq_kw:
            freq_df = pd.DataFrame(freq_kw)[["word", "count"]]
            st.dataframe(freq_df, width='stretch', hide_index=True)
        else:
            st.info("No frequency data.")

    with col_k2:
        st.write("**Unique Sentiment Drivers (TF-IDF)**")
        tfidf_kw = data.get("tfidf_keywords", [])
        if tfidf_kw:
            tfidf_df = pd.DataFrame(tfidf_kw)[["word", "score"]]
            st.dataframe(tfidf_df, width='stretch', hide_index=True)
        else:
            st.info("No TF-IDF data.")

def render_results_table_v2(results_df):
    """
    Renders the fully searchable and sortable results table with SEARCH and PAGINATION.
    """
    @st.fragment
    def _results_fragment():
        st.subheader("📋 Raw Data Review")
        
        if st.session_state.get("clear_res"):
            st.session_state.res_q_in = ""
            st.session_state.clear_res = False

        with st.form("results_search_form"):
            c_in, c_search, c_clear = st.columns([3, 1, 1])
            with c_in:
                res_query = st.text_input("Search ID", key="res_q_in", label_visibility="collapsed", placeholder="Enter ID...")
            with c_search:
                st.form_submit_button("Search")
            with c_clear:
                if st.form_submit_button("Clear"):
                    st.session_state.clear_res = True
                    st.rerun(scope="fragment")

        col1, col2 = st.columns(2)
        with col1:
            sentiment_filter = st.selectbox(
                "Filter by Sentiment",
                ["All", "Positive", "Negative", "Neutral"],
                key="sentiment_filter"
            )
        with col2:
            sort_order = st.selectbox(
                "Sort by Score",
                ["Descending (High to Low)", "Ascending (Low to High)"],
                key="sort_order"
            )

        res_df_display = results_df.copy()

        # Apply fast local filtering
        if res_query:
            query_lower = res_query.strip().lower()
            exclude = {'score', 'sentiment_label', 'feedback_text', '_search_id', '_search_all'}
            id_col = None
            for c in res_df_display.columns:
                if c in exclude: continue
                if any(k in c.lower() for k in ["userid", "user_id", "customerid", "customer_id", "id"]):
                    id_col = c
                    break
            
            if id_col:
                res_df_display = res_df_display[res_df_display[id_col].astype(str).str.strip().str.lower() == query_lower]
            else:
                str_cols = [c for c in res_df_display.columns if c not in exclude]
                mask = pd.Series(False, index=res_df_display.index)
                for col in str_cols:
                    mask |= res_df_display[col].astype(str).str.lower().str.contains(query_lower, na=False, regex=False)
                res_df_display = res_df_display[mask]

        # Use the correct renamed column for sentiment filtering
        sentiment_col = 'sentiment_label' if 'sentiment_label' in res_df_display.columns else 'label'
        if sentiment_filter != "All" and sentiment_col in res_df_display.columns:
            res_df_display = res_df_display[res_df_display[sentiment_col] == sentiment_filter.upper()]

        if 'score' in res_df_display.columns:
            ascending = (sort_order == "Ascending (Low to High)")
            res_df_display = res_df_display.sort_values("score", ascending=ascending)

        if res_df_display.empty:
            st.warning("⚠️ No records found.")
            return

        # --- Pagination Logic ---
        items_per_page = 10
        total_items = len(res_df_display)
        total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1

        if "feedback_page_num" not in st.session_state:
            st.session_state.feedback_page_num = 1
        if st.session_state.feedback_page_num > total_pages:
            st.session_state.feedback_page_num = total_pages

        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("⬅️ Previous", disabled=st.session_state.feedback_page_num <= 1, key="fb_prev", width='stretch'):
                st.session_state.feedback_page_num -= 1
                try: st.rerun(scope="fragment")
                except: st.rerun()
        with p3:
            if st.button("Next ➡️", disabled=st.session_state.feedback_page_num >= total_pages, key="fb_next", width='stretch'):
                st.session_state.feedback_page_num += 1
                try: st.rerun(scope="fragment")
                except: st.rerun()

        start_idx = (st.session_state.feedback_page_num - 1) * items_per_page
        end_idx = start_idx + items_per_page
        with p2:
            st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Page <b>{st.session_state.feedback_page_num}</b> of <b>{total_pages}</b><br><small>{total_items} results total</small></div>", unsafe_allow_html=True)

        display_cols = [c for c in res_df_display.columns if c not in ['_search_id', '_search_all']]
        df_page = res_df_display.iloc[start_idx:end_idx]
        st.dataframe(df_page[display_cols], width='stretch', hide_index=True)
    
    _results_fragment()
