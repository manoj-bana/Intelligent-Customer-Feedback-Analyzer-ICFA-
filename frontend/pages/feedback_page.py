import base64
import io
import requests
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from analytics_dashboard.charts import (
    generate_sentiment_bar_chart,
    generate_sentiment_line_chart,
    generate_sentiment_pie_chart,
    generate_keyword_frequency_chart
)
from analytics_dashboard.data_loader import aggregate_user_data
from frontend.utils.export_utils import export_to_format

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

    # --- Data Preparation ---
    results_df = pd.DataFrame(data["results"])
    if 'label' in results_df.columns:
        results_df.rename(columns={'label': 'sentiment_label'}, inplace=True)
    if 'review' in results_df.columns:
        results_df.rename(columns={'review': 'feedback_text'}, inplace=True)

    df_enriched = None
    if "enriched_csv" in data and data["enriched_csv"]:
        try:
            csv_bytes = base64.b64decode(data["enriched_csv"])
            df_enriched = pd.read_csv(io.BytesIO(csv_bytes))
            df_enriched = normalize_dataframe_columns(df_enriched)
        except Exception as e:
            st.error(f"Error parsing enriched dataset: {e}")

    # Export Section
    if df_enriched is not None or not results_df.empty:
        st.subheader("📥 Export Analysis Report")
        col_fmt, col_btn = st.columns([1, 1])
        with col_fmt:
            export_fmt = st.selectbox("Select Format", ["CSV", "Excel", "DOCX", "PDF"], key="feedback_export_fmt")
        
        df_export = df_enriched if df_enriched is not None else results_df
        export_data = export_to_format(df_export, export_fmt, title="Customer Feedback Sentiment Report")
        
        with col_btn:
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
    
    st.divider()

    # --- User-Level Aggregation ---
    user_agg_data = data.get("user_engagement")
    if user_agg_data or df_enriched is not None:
        with st.expander("👤 User-Specific Engagement Analysis", expanded=False):
            st.write("Identifies high-volume contributors and their dominant sentiment profiles.")
            
            agg_df = None
            if user_agg_data:
                agg_df = pd.DataFrame(user_agg_data)
            elif df_enriched is not None:
                agg_df = aggregate_user_data(df_enriched)
            
            if agg_df is not None and not agg_df.empty:
                st.dataframe(agg_df, use_container_width=True, hide_index=True)
            else:
                st.info("User-level data (IDs) not identified in this dataset.")
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
            st.dataframe(pd.DataFrame(freq_kw)[["word", "count"]], use_container_width=True, hide_index=True)
        else:
            st.info("No frequency data.")

    with col_k2:
        st.write("**Unique Sentiment Drivers (TF-IDF)**")
        tfidf_kw = data.get("tfidf_keywords", [])
        if tfidf_kw:
            st.dataframe(pd.DataFrame(tfidf_kw)[["word", "score"]], use_container_width=True, hide_index=True)
        else:
            st.info("No TF-IDF data.")

def render_results_table(data):
    """
    Renders an action-oriented results table focusing on outliers.
    """
    st.subheader("📋 Critical Review Feed")
    st.caption("Focus on reviews with high confidence scores to identify core issues or success stories.")

    res_df = pd.DataFrame(data["results"])

    c1, c2 = st.columns([1, 1])
    with c1:
        sentiment_filter = st.selectbox("Priority Filter", ["All", "Positive", "Negative", "Neutral"], key="prio_filter")
    with c2:
        view_mode = st.radio("View Mode", ["Top 50 Outliers", "All Matching"], horizontal=True, key="view_mode")

    if sentiment_filter != "All":
        res_df = res_df[res_df["label"] == sentiment_filter.upper()]

    if 'score' in res_df.columns:
        res_df = res_df.sort_values("score", ascending=False)

    display_df = res_df.head(50) if view_mode == "Top 50 Outliers" else res_df

    st.dataframe(
        display_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "review": st.column_config.TextColumn("Customer Review", width="large"),
            "label": st.column_config.TextColumn("Sentiment"),
            "score": st.column_config.NumberColumn("Confidence")
        }
    )
