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
        with st.spinner("Fetching analysis results..."):
            try:
                res = requests.get(f"{API_URL}/ingest/results/{case_id}", timeout=30)
                if res.status_code == 200:
                    st.session_state.analysis_results = res.json()
                else:
                    st.error(f"Error fetching results: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    if "analysis_results" in st.session_state:
        show_results(st.session_state.analysis_results)

def show_results(data):
    """
    Renders the analysis results, including metric cards, charts, and detailed keyword data.
    """
    st.success(f"✅ Analyzed {data['total']} reviews!")

    # --- Metric Cards ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Positive Reviews", data["positive"], delta="High satisfaction", delta_color="normal")
    m2.metric("Negative Reviews", data["negative"], delta="Improvement areas", delta_color="inverse")
    m3.metric("Neutral Reviews", data["neutral"])
    st.divider()

    # --- Move Global Search Bar logic back into local sections later ---

    # --- Data Preparation (Cached) ---
    results_df = get_processed_results(data["results"])
    df_enriched = get_processed_enriched(data.get("enriched_csv"))






    # Export Section
    if df_enriched is not None or not results_df.empty:
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

    if 'sentiment_label' not in df_to_plot.columns:
        df_to_plot['sentiment_label'] = df_to_plot.get('label', 'UNKNOWN')

    # --- Visualizations Pipeline ---
    render_visualizations(data, df_to_plot)
    
    # --- User-Level Aggregation ---
    if df_enriched is not None:
        # Cached aggregation is critical for speed on large datasets
        agg_df_all = get_cached_aggregation(df_enriched)
        
        @st.fragment
        def render_user_aggregation():
            st.subheader("👤 Per-User Analysis")
            
            # Move CLEAR logic ABOVE the widget instantiation
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
            elif agg_df is not None:
                st.caption("Showing preview of first 1,000 users. Use 'Search ID' to find specific customers.")
                agg_df = agg_df.head(1000)

            if agg_df is not None and not agg_df.empty:
                st.dataframe(agg_df, use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ No records found.")
        
        render_user_aggregation()

        st.divider()


    # --- Keyword Discovery ---
    render_keyword_tabs(data)

    st.divider()

    # --- Detailed Results Table ---
    render_results_table(data, results_df)


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
        df.rename(columns={text_col: 'feedback_text'}, inplace=True)
    return df

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

def render_results_table(data, results_df):
    """
    Renders the fully searchable and sortable results table as a fragment.
    Only this section re-renders on search/clear, not the entire page.
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
            
            # Find the ID column directly (not from cache)
            exclude = {'score', 'sentiment_label', 'feedback_text', '_search_id', '_search_all'}
            id_col = None
            for c in res_df_display.columns:
                if c in exclude:
                    continue
                cl = c.lower()
                if any(k in cl for k in ["userid", "user_id", "customerid", "customer_id", "customer id", "id"]):
                    id_col = c
                    break
            
            if id_col:
                # Exact match on ID column — "540" finds ONLY Id=540
                res_df_display = res_df_display[
                    res_df_display[id_col].astype(str).str.strip().str.lower() == query_lower
                ]
            else:
                # No ID column found — search all text columns
                str_cols = [c for c in res_df_display.columns if c not in exclude]
                mask = pd.Series(False, index=res_df_display.index)
                for col in str_cols:
                    mask |= res_df_display[col].astype(str).str.lower().str.contains(query_lower, na=False, regex=False)
                res_df_display = res_df_display[mask]
        else:
            st.caption("Showing preview of first 1,000 records. Use 'Search ID' to find specific records.")
            res_df_display = res_df_display.head(1000)

        # Use the correct renamed column for sentiment filtering
        sentiment_col = 'sentiment_label' if 'sentiment_label' in res_df_display.columns else 'label'
        if sentiment_filter != "All" and sentiment_col in res_df_display.columns:
            res_df_display = res_df_display[res_df_display[sentiment_col] == sentiment_filter.upper()]

        if 'score' in res_df_display.columns:
            ascending = (sort_order == "Ascending (Low to High)")
            res_df_display = res_df_display.sort_values("score", ascending=ascending)

        # Hide internal search columns from display
        display_cols = [c for c in res_df_display.columns if c not in ['_search_id', '_search_all']]

        if res_df_display.empty and res_query:
            st.warning("⚠️ No records found.")
        else:
            st.dataframe(res_df_display[display_cols], use_container_width=True, hide_index=True)
    
    _results_fragment()
