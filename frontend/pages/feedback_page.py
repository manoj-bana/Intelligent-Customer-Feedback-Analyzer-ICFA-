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

API_URL = "http://127.0.0.1:8000"

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
        case_id = case_mapping[selected_case_label]
        with st.spinner("Fetching report data..."):
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

    # --- Data Preparation ---
    results_df = pd.DataFrame(data["results"])
    if 'label' in results_df.columns:
        results_df.rename(columns={'label': 'sentiment_label'}, inplace=True)
    if 'review' in results_df.columns:
        results_df.rename(columns={'review': 'feedback_text'}, inplace=True)

    df_enriched = None
    # Check if Enriched CSV is available for Download and Data Parsing
    if "enriched_csv" in data and data["enriched_csv"]:
        csv_bytes = base64.b64decode(data["enriched_csv"])
        st.download_button(
            label="⬇️ Download Enriched Results (CSV)",
            data=csv_bytes,
            file_name="feedback_sentiment_report.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.divider()
        try:
            df_enriched = pd.read_csv(io.BytesIO(csv_bytes))
            df_enriched = normalize_dataframe_columns(df_enriched)
        except Exception as e:
            st.error(f"Error parsing enriched dataset: {e}")

    df_to_plot = df_enriched if df_enriched is not None and not df_enriched.empty else results_df

    if 'sentiment_label' not in df_to_plot.columns:
        df_to_plot['sentiment_label'] = df_to_plot.get('label', 'UNKNOWN')

    # --- Visualizations Pipeline ---
    render_visualizations(data, df_to_plot)
    
    st.divider()

    # --- User-Level Aggregation ---
    if df_enriched is not None:
        st.subheader("👤 Per-User Analysis")
        agg_df = aggregate_user_data(df_enriched)
        if agg_df is not None and not agg_df.empty:
            st.dataframe(agg_df, use_container_width=True, hide_index=True)
        else:
            st.info("Insufficient data for user-level aggregation.")
        st.divider()

    # --- Keyword Discovery ---
    render_keyword_tabs(data)

    st.divider()

    # --- Detailed Results Table ---
    render_results_table(data)

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

def render_results_table(data):
    """
    Renders the fully searchable and sortable results table.
    """
    st.subheader("📋 Raw Data Review")

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

    res_df_display = pd.DataFrame(data["results"])

    if sentiment_filter != "All":
        res_df_display = res_df_display[res_df_display["label"] == sentiment_filter.upper()]

    if 'score' in res_df_display.columns:
        ascending = (sort_order == "Ascending (Low to High)")
        res_df_display = res_df_display.sort_values("score", ascending=ascending)

    st.dataframe(res_df_display, use_container_width=True, hide_index=True)
