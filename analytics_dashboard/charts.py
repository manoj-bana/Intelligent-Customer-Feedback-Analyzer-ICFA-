import streamlit as st
import matplotlib.pyplot as plt
import plotly.express as px
import pandas as pd
import io

COLOR_MAP = {
    'POSITIVE': '#28a745',
    'NEUTRAL': '#6c757d',
    'NEGATIVE': '#dc3545'
}

@st.cache_data
def _build_bar_chart(sentiment_series_tuple):
    """Cached: builds Plotly bar chart JSON from sentiment counts."""
    sentiment_counts = pd.Series(dict(sentiment_series_tuple)).reset_index()
    sentiment_counts.columns = ['Sentiment', 'Count']
    fig = px.bar(sentiment_counts, x='Sentiment', y='Count', color='Sentiment',
                 color_discrete_map=COLOR_MAP, title='Sentiment Distribution')
    return fig

def generate_sentiment_bar_chart(df):
    counts = df['sentiment_label'].str.upper().value_counts()
    fig = _build_bar_chart(tuple(counts.items()))
    st.plotly_chart(fig, width='stretch')

@st.cache_data
def _build_pie_chart(sentiment_series_tuple):
    """Cached: builds Plotly pie chart JSON from sentiment counts."""
    sentiment_counts = pd.Series(dict(sentiment_series_tuple)).reset_index()
    sentiment_counts.columns = ['Sentiment', 'Count']
    fig = px.pie(sentiment_counts, names='Sentiment', values='Count', color='Sentiment',
                 color_discrete_map=COLOR_MAP, title='Sentiment Share')
    return fig

def generate_sentiment_pie_chart(df):
    counts = df['sentiment_label'].str.upper().value_counts()
    fig = _build_pie_chart(tuple(counts.items()))
    st.plotly_chart(fig, width='stretch')

@st.cache_data
def _build_line_chart(trend_data_tuple):
    """Cached: builds Plotly line chart JSON from trend data."""
    trend = pd.DataFrame(trend_data_tuple, columns=['date_only', 'sentiment_label', 'Count'])
    fig = px.line(trend, x='date_only', y='Count', color='sentiment_label',
                  color_discrete_map=COLOR_MAP, title='Sentiment Over Time', markers=True)
    return fig

def generate_sentiment_line_chart(df):
    # More robust date column detection
    # First exact math
    date_candidates = ['date', 'timestamp', 'created_at', 'time', 'review date', 'review_date', 'year', 'dt']
    date_col = next((col for col in date_candidates if col.lower() in [c.lower() for c in df.columns]), None)
    
    
    # Fallback substring match (e.g., 'ReviewDate', 'CreationTime')
    if not date_col:
        for c in df.columns:
            if 'date' in c.lower() or 'time' in c.lower() or 'timestamp' in c.lower():
                date_col = c
                break
                
    if date_col:
        actual_date_col = next((col for col in df.columns if col.lower() == date_col.lower()), date_col)
        
        # Work on a copy to avoid modifying cached/frozen data
        df_work = df.copy()
        
        # In case the time column is unix epoch (like in Amazon datasets)
        if pd.api.types.is_numeric_dtype(df_work[actual_date_col]):
            df_work['date_only'] = pd.to_datetime(df_work[actual_date_col], unit='s', errors='coerce').dt.date
        else:
            df_work['date_only'] = pd.to_datetime(df_work[actual_date_col], errors='coerce').dt.date
            
        df_valid_dates = df_work.dropna(subset=['date_only'])
        
        if not df_valid_dates.empty:
            trend = df_valid_dates.groupby(['date_only', 'sentiment_label']).size().reset_index(name='Count')
            trend['sentiment_label'] = trend['sentiment_label'].str.upper()
            # Convert to tuple of tuples for caching
            trend_tuple = tuple(trend.itertuples(index=False, name=None))
            fig = _build_line_chart(trend_tuple)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No valid dates found in column '{actual_date_col}' for Sentiment Over Time chart.")
    else:
        st.info(f"No timeline data (date/time column) available for Sentiment Over Time chart. Available columns: {list(df.columns)}")


@st.cache_data
def _build_keyword_chart(freq_data_tuple):
    """Cached: builds Plotly keyword frequency chart."""
    df_kw = pd.DataFrame(list(freq_data_tuple), columns=['Keyword', 'Frequency'])
    fig = px.bar(df_kw, x='Frequency', y='Keyword', orientation='h', title='Top 10 Keywords',
                 color_discrete_sequence=['#17a2b8'])
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    return fig

@st.cache_data
def generate_keyword_frequency_chart(freq_data):
    if not freq_data:
        st.info("No keywords available.")
        return
    df_kw = pd.DataFrame(freq_data, columns=['Keyword', 'Frequency'])
    fig = px.bar(df_kw, x='Frequency', y='Keyword', orientation='h', title='Top 10 Keywords',
                 color_discrete_sequence=['#17a2b8'])
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)
