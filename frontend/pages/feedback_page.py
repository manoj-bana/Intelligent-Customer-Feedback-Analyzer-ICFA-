import base64
import io
import requests
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud

from analytics_dashboard.charts import (
    generate_sentiment_bar_chart,
    generate_sentiment_line_chart,
    generate_sentiment_pie_chart,
    generate_keyword_frequency_chart,
    generate_wordcloud
)
from analytics_dashboard.data_loader import aggregate_user_data
from frontend.utils.export_utils import export_to_format

API_URL = "http://127.0.0.1:8000"

@st.cache_data
def get_cached_aggregation(df):
    """Caches the expensive user-level data aggregation."""
    agg = aggregate_user_data(df)
    if agg is not None:
         id_cols = [c for c in agg.columns if any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
         if id_cols:
              agg['_search_id'] = agg[id_cols[0]].astype(str).str.lower()
    return agg

@st.cache_data
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

@st.cache_data
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
    except Exception: return None

def show():
    """
    Main entry point for the Sentiment Analysis report page. 
    Handles dataset selection and report rendering.
    """
    st.title("💬 Sentiment Analysis")
    st.markdown("Select an ingested dataset to view the sentiment analysis report.")
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

    # Get completed sentiment datasets
    sentiment_cases = [
        c for c in cases_data 
        if c.get("task_type") == "Sentiment Analysis" and c.get("review_status") == "Completed"
    ]

    if not sentiment_cases:
        st.info(
            "No completed Sentiment Analysis datasets found. "
            "Go to 'Document Ingestion' to upload one."
        )
        return

    # Map labels to case IDs
    case_mapping = {
        f"{c['filename']} (ID: {c['case_id']})": c['case_id'] for c in sentiment_cases
    }
    
    selected_case_label = st.selectbox(
        "Select Dataset", 
        list(case_mapping.keys()), 
        key="select_sentiment_dataset"
    )
    if st.button("📊 View Report", use_container_width=True, key="btn_view_sentiment"):
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
                        st.session_state.processed_agg_df = None
                        
                else:
                    st.error(f"Error fetching results: {res.text}")
            except Exception as e:
                st.error(f"Processing error: {e}")

    if "analysis_results" in st.session_state:
        show_results(
            st.session_state.analysis_results,
            st.session_state.get("processed_results_df"),
            st.session_state.get("processed_enriched_df"),
            st.session_state.get("processed_agg_df")
        )

def show_results(data, results_df, df_enriched, agg_df):
    """
    Renders optimized reports using pre-processed dataframes with search support.
    """
    st.success(f"✅ Analyzed {data['total']} reviews!")

    # --- Metric Cards ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Positive Reviews", data["positive"], delta="High satisfaction", delta_color="normal")
    m2.metric("Negative Reviews", data["negative"], delta="Improvement areas", delta_color="inverse")
    m3.metric("Neutral Reviews", data["neutral"])
    st.divider()

    # Export Section
    if df_enriched is not None or (results_df is not None and not results_df.empty):
        st.subheader("📥 Export Analysis Report")
        col_fmt, col_btn = st.columns([1, 1])
        with col_fmt:
            export_fmt = st.selectbox("Select Format", ["CSV", "Excel", "DOCX", "PDF"], key="feedback_export_fmt")
        
        df_export = df_enriched if df_enriched is not None else results_df
        export_data = export_to_format(df_export, export_fmt, title="Customer Feedback Sentiment Report")
        
        with col_btn:
            st.write("") # Padding
            st.download_button(
                label=f"⬇️ Download as {export_fmt}",
                data=export_data,
                file_name=f"feedback_report.{export_fmt.lower()}",
                mime="application/octet-stream",
                use_container_width=True,
            )
        st.divider()

    df_to_plot = df_enriched if df_enriched is not None and not df_enriched.empty else results_df
    if df_to_plot is not None and 'sentiment_label' not in df_to_plot.columns:
        df_to_plot['sentiment_label'] = df_to_plot.get('label', 'UNKNOWN')

    # --- Visualizations Pipeline ---
    render_visualizations_fragment(data, df_to_plot)
    
    # --- User-Level Aggregation ---
    if df_enriched is not None:
        render_user_aggregation_fragment_v2(agg_df)

    # --- Keyword Discovery ---
    render_keyword_tabs(data)

    st.divider()

    # --- Detailed Results Table ---
    render_results_table_v2(results_df)

@st.fragment
def render_user_aggregation_fragment_v2(agg_df_all):
    """
    Renders user-level statistics with SEARCH and PAGINATION.
    """
    st.subheader("👤 Per-User Analysis")
    
    if st.session_state.get("clear_agg"):
        st.session_state.agg_q_in = ""
        st.session_state.clear_agg = False
        
    with st.form("agg_search_form"):
        c_in, c_search, c_clear = st.columns([3, 1, 1])
        with c_in:
            agg_query = st.text_input("Search ID", key="agg_q_in", label_visibility="collapsed", placeholder="Enter ID...")
        with c_search:
            st.form_submit_button("Search")
        with c_clear:
            if st.form_submit_button("Clear"):
                st.session_state.clear_agg = True
                st.rerun(scope="fragment")

    agg_df = agg_df_all.copy() if agg_df_all is not None else None
    
    # Fast local filtering
    if agg_query and agg_df is not None:
        if '_search_id' in agg_df.columns:
             agg_df = agg_df[agg_df['_search_id'].str.startswith(agg_query.strip().lower())]
        else:
            id_cols = [c for c in agg_df.columns if any(k in c.lower() for k in ["userid", "user id", "customerid", "customer id", "user", "id"])]
            if id_cols:
                agg_df = agg_df[agg_df[id_cols[0]].astype(str).str.lower().str.startswith(agg_query.strip().lower())]
    
    if agg_df is not None and not agg_df.empty:
        # --- Pagination Logic ---
        items_per_page = 10
        total_items = len(agg_df)
        total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
        
        if "user_agg_page" not in st.session_state:
            st.session_state.user_agg_page = 1
        if st.session_state.user_agg_page > total_pages:
            st.session_state.user_agg_page = total_pages
            
        ua1, ua2, ua3 = st.columns([1, 2, 1])
        with ua1:
            if st.button("⬅️ Prev", disabled=st.session_state.user_agg_page <= 1, key="ua_prev", use_container_width=True):
                st.session_state.user_agg_page -= 1
                try: st.rerun(scope="fragment")
                except: st.rerun()
        with ua3:
            if st.button("Next ➡️", disabled=st.session_state.user_agg_page >= total_pages, key="ua_next", use_container_width=True):
                st.session_state.user_agg_page += 1
                try: st.rerun(scope="fragment")
                except: st.rerun()

        start_idx = (st.session_state.user_agg_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        with ua2:
            st.markdown(f"<p style='text-align:center;'>Page <b>{st.session_state.user_agg_page}</b> of <b>{total_pages}</b></p>", unsafe_allow_html=True)
                
        df_page = agg_df.iloc[start_idx:end_idx]
        st.dataframe(df_page, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No records found.")
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
        "Sentiment Trend Analysis", 
        "Visual Word Cloud"
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
        c4, c5 = st.columns(2)
        with c4:
            generate_sentiment_line_chart(df_to_plot)
        with c5:
            render_wordcloud_chart(df_to_plot)
                
    elif selected_chart == "Sentiment Distribution (Bar)":
        generate_sentiment_bar_chart(df_to_plot)
    elif selected_chart == "Sentiment Proportions (Pie)":
        generate_sentiment_pie_chart(df_to_plot)
    elif selected_chart == "Keyword Frequency Report":
        render_freq_chart(data)
    elif selected_chart == "Sentiment Trend Analysis":
        generate_sentiment_line_chart(df_to_plot)
    elif selected_chart == "Visual Word Cloud":
        render_wordcloud_chart(df_to_plot)

def render_freq_chart(data):
    """Helper to render frequency chart from results data."""
    freq_kw = data.get("freq_keywords") or data.get("keywords", [])
    if freq_kw:
        freq_for_charts = [(item["word"], item["count"]) for item in freq_kw[:10]]
        generate_keyword_frequency_chart(freq_for_charts)
    else:
        st.info("No frequency keywords available.")

def render_wordcloud_chart(df):
    """Helper to render wordcloud from dataframe text."""
    all_text = " ".join(df.get('feedback_text', pd.Series([])).dropna().astype(str))
    if all_text:
        generate_wordcloud(all_text)
    else:
        st.info("No text available for word cloud.")

def render_keyword_tabs(data):
    """
    Renders the detailed keyword extraction tabs.
    """
    st.subheader("🔑 Keyword Extraction")
    tab_freq, tab_tfidf = st.tabs(["📊 Frequency Count", "📐 TF-IDF Scoring"])

    with tab_freq:
        st.caption("Common terms ranked by raw frequency across the dataset.")
        freq_kw = data.get("freq_keywords") or data.get("keywords", [])
        if freq_kw:
            freq_df = pd.DataFrame(freq_kw)[["word", "count"]]
            st.dataframe(freq_df, use_container_width=True, hide_index=True)
        else:
            st.info("Frequency data unavailable.")

    with tab_tfidf:
        st.caption("Terms ranked by TF-IDF scoring, highlighting uniquely significant words.")
        tfidf_kw = data.get("tfidf_keywords", [])
        if tfidf_kw:
            tfidf_df = pd.DataFrame(tfidf_kw)[["word", "score"]]
            st.dataframe(tfidf_df, use_container_width=True, hide_index=True)
        else:
            st.info("TF-IDF data unavailable.")

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
            if st.button("⬅️ Previous", disabled=st.session_state.feedback_page_num <= 1, key="fb_prev", use_container_width=True):
                st.session_state.feedback_page_num -= 1
                try: st.rerun(scope="fragment")
                except: st.rerun()
        with p3:
            if st.button("Next ➡️", disabled=st.session_state.feedback_page_num >= total_pages, key="fb_next", use_container_width=True):
                st.session_state.feedback_page_num += 1
                try: st.rerun(scope="fragment")
                except: st.rerun()

        start_idx = (st.session_state.feedback_page_num - 1) * items_per_page
        end_idx = start_idx + items_per_page
        with p2:
            st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Page <b>{st.session_state.feedback_page_num}</b> of <b>{total_pages}</b><br><small>{total_items} results total</small></div>", unsafe_allow_html=True)

        display_cols = [c for c in res_df_display.columns if c not in ['_search_id', '_search_all']]
        df_page = res_df_display.iloc[start_idx:end_idx]
        st.dataframe(df_page[display_cols], use_container_width=True, hide_index=True)
    
    _results_fragment()
