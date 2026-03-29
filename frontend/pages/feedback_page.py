import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import base64
import io

API_URL = "http://127.0.0.1:8000"


def show():
    st.title("💬 Sentiment Analysis")
    st.markdown(
        "Upload a CSV with a column named: `review`, `feedback`, `comment`, or `text`"
    )
    st.divider()

    uploaded_file = st.file_uploader("📂 Upload CSV file", type=["csv"])

    if uploaded_file:
        df_preview = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)
        st.markdown("**Preview (first 5 rows):**")
        st.dataframe(df_preview.head(), use_container_width=True)
        st.markdown(f"Total rows: `{len(df_preview)}`")
        st.divider()

        if st.button("🔍 Analyze Sentiment", use_container_width=True):
            try:
                with st.spinner("Uploading and starting job... (first run may take 1-2 mins)"):
                    import time
                    response = requests.post(
                        f"{API_URL}/feedback/analyze",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                        timeout=120
                    )
                if response.status_code == 200:
                    resp_json = response.json()
                    job_id = resp_json.get("job_id")
                    if job_id:
                        progress_container = st.empty()
                        with st.spinner("Job started..."):
                            while True:
                                res_status = requests.get(f"{API_URL}/feedback/result/{job_id}", timeout=60).json()
                                if res_status.get("status") == "completed":
                                    st.session_state.analysis_results = res_status.get("data")
                                    progress_container.empty()
                                    break
                                elif res_status.get("status") == "failed":
                                    st.error(f"Processing failed: {res_status.get('error')}")
                                    progress_container.empty()
                                    break
                                else:
                                    msg = res_status.get("message", "Processing in background...")
                                    progress_container.info(f"⏳ {msg}")
                                time.sleep(0.3)
                    else:
                        st.session_state.analysis_results = resp_json
                else:
                    st.error(f"API Error: {response.text}")
            except requests.exceptions.ConnectionError:
                st.warning("⚠️ Backend not running. Showing mock results for UI demo.")
                st.session_state.analysis_results = mock_result()

    if "analysis_results" in st.session_state:
        show_results(st.session_state.analysis_results)


def show_results(data):
    st.success(f"✅ Analyzed {data['total']} reviews!")

    # ── Metric cards ──
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Positive", data["positive"])
    col2.metric("❌ Negative", data["negative"])
    col3.metric("😐 Neutral",  data["neutral"])
    st.divider()

    # ── Phase 3: Download enriched CSV (with SentimentLabel & SentimentScore columns) ──
    if "enriched_csv" in data and data["enriched_csv"]:
        csv_bytes = base64.b64decode(data["enriched_csv"])
        st.download_button(
            label="⬇️ Download Results CSV (with SentimentLabel & SentimentScore columns)",
            data=csv_bytes,
            file_name="feedback_with_sentiment.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.divider()

    # ── Sentiment pie chart ──
    col_chart, col_wc = st.columns(2)

    with col_chart:
        st.subheader("📊 Sentiment Split")
        labels, sizes, colors = [], [], []
        for label, count, color in [
            ("Positive", data["positive"], "#31F738"),
            ("Negative", data["negative"], "#D82114"),
            ("Neutral",  data["neutral"],  "#8C7777"),
        ]:
            if count > 0:
                labels.append(label)
                sizes.append(count)
                colors.append(color)
        fig, ax = plt.subplots()
        ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%")
        st.pyplot(fig)

    # ── Phase 4: Word Cloud ──
    with col_wc:
        st.subheader("☁️ Word Cloud")
        # Build word frequency dict from freq_keywords for word cloud
        kw_source = data.get("freq_keywords") or data.get("keywords", [])
        if kw_source:
            # WordCloud needs a {word: weight} dict
            word_freq = {item["word"]: item["count"] for item in kw_source}
            wc = WordCloud(
                width=600,
                height=350,
                background_color="white",
                colormap="RdYlGn",       # red → yellow → green palette
                max_words=50,
            ).generate_from_frequencies(word_freq)
            fig_wc, ax_wc = plt.subplots(figsize=(6, 3.5))
            ax_wc.imshow(wc, interpolation="bilinear")
            ax_wc.axis("off")
            st.pyplot(fig_wc)
        else:
            st.info("No keywords available for word cloud.")

    st.divider()

    # ── Phase 4: Keyword Extraction — two tabs (Frequency vs TF-IDF) ──
    st.subheader("🔑 Keyword Extraction")
    tab_freq, tab_tfidf = st.tabs(["📊 Frequency Count", "📐 TF-IDF"])

    with tab_freq:
        st.caption(
            "**Frequency Count** — words ranked by how many times they appear across all reviews. "
            "Simple and fast."
        )
        freq_kw = data.get("freq_keywords") or data.get("keywords", [])
        if freq_kw:
            freq_df = pd.DataFrame(freq_kw)[["word", "count"]]
            st.bar_chart(freq_df.set_index("word")["count"])
            st.dataframe(freq_df, use_container_width=True)
        else:
            st.info("No frequency keywords available.")

    with tab_tfidf:
        st.caption(
            "**TF-IDF (Term Frequency – Inverse Document Frequency)** — words scored by how "
            "important they are *within* a review vs. how common they are *across all* reviews. "
            "Highlights unique and meaningful terms rather than just frequent ones."
        )
        tfidf_kw = data.get("tfidf_keywords", [])
        if tfidf_kw:
            tfidf_df = pd.DataFrame(tfidf_kw)[["word", "score"]]
            st.bar_chart(tfidf_df.set_index("word")["score"])
            st.dataframe(tfidf_df, use_container_width=True)
        else:
            st.info("No TF-IDF keywords available.")

    st.divider()

    # ── All review results table (with filter & sort) ──
    st.subheader("📋 All Review Results")

    col1, col2 = st.columns(2)
    with col1:
        sentiment_filter = st.selectbox(
            "Filter by sentiment",
            ["All", "Positive", "Negative", "Neutral"],
            key="sentiment_filter"
        )
    with col2:
        sort_order = st.selectbox(
            "Sort by sentiment score",
            ["Descending (High to Low)", "Ascending (Low to High)"],
            key="sort_order"
        )

    results_df = pd.DataFrame(data["results"])

    if sentiment_filter != "All":
        results_df = results_df[results_df["label"] == sentiment_filter.upper()]

    ascending = sort_order == "Ascending (Low to High)"
    results_df = results_df.sort_values("score", ascending=ascending)

    st.dataframe(results_df, use_container_width=True)


def mock_result():
    """Fallback mock data when backend is not running."""
    import math
    freq_kw   = [
        {"word": "great",   "count": 8, "method": "frequency"},
        {"word": "product", "count": 6, "method": "frequency"},
        {"word": "love",    "count": 5, "method": "frequency"},
        {"word": "quality", "count": 4, "method": "frequency"},
        {"word": "service", "count": 3, "method": "frequency"},
    ]
    tfidf_kw  = [
        {"word": "great",   "score": 0.312, "method": "tfidf"},
        {"word": "product", "score": 0.289, "method": "tfidf"},
        {"word": "quality", "score": 0.201, "method": "tfidf"},
        {"word": "love",    "score": 0.187, "method": "tfidf"},
        {"word": "service", "score": 0.143, "method": "tfidf"},
    ]
    return {
        "total": 5, "positive": 3, "negative": 1, "neutral": 1,
        "results": [
            {"review": "Great product!",  "label": "POSITIVE", "score": 0.99},
            {"review": "Worst ever.",     "label": "NEGATIVE", "score": 0.97},
            {"review": "It was okay.",    "label": "POSITIVE", "score": 0.61},
            {"review": "Love it!",        "label": "POSITIVE", "score": 0.98},
            {"review": "Not bad.",        "label": "NEUTRAL",  "score": 0.55},
        ],
        "keywords":       freq_kw,
        "freq_keywords":  freq_kw,
        "tfidf_keywords": tfidf_kw,
        "enriched_csv":   None,
    }


