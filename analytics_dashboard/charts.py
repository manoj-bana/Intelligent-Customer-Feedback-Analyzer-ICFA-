import streamlit as st
import matplotlib.pyplot as plt
import plotly.express as px
from wordcloud import WordCloud
import pandas as pd

COLOR_MAP = {
    'POSITIVE': '#28a745',
    'NEUTRAL': '#6c757d',
    'NEGATIVE': '#dc3545'
}

def generate_sentiment_bar_chart(df):
    sentiment_counts = df['sentiment_label'].str.upper().value_counts().reset_index()
    sentiment_counts.columns = ['Sentiment', 'Count']
    fig = px.bar(sentiment_counts, x='Sentiment', y='Count', color='Sentiment',
                 color_discrete_map=COLOR_MAP, title='Sentiment Distribution')
    st.plotly_chart(fig, use_container_width=True)

def generate_sentiment_line_chart(df):
    date_col = next((col for col in ['date', 'timestamp', 'created_at', 'time'] if col.lower() in [c.lower() for c in df.columns]), None)
    if date_col:
        actual_date_col = next(col for col in df.columns if col.lower() == date_col.lower())
        
        # In case the time column is unix epoch (like in Amazon datasets)
        if pd.api.types.is_numeric_dtype(df[actual_date_col]):
            df['date_only'] = pd.to_datetime(df[actual_date_col], unit='s', errors='coerce').dt.date
        else:
            df['date_only'] = pd.to_datetime(df[actual_date_col], errors='coerce').dt.date
            
        df_valid_dates = df.dropna(subset=['date_only'])
        
        if not df_valid_dates.empty:
            trend = df_valid_dates.groupby(['date_only', 'sentiment_label']).size().reset_index(name='Count')
            trend['sentiment_label'] = trend['sentiment_label'].str.upper()
            fig = px.line(trend, x='date_only', y='Count', color='sentiment_label', 
                          color_discrete_map=COLOR_MAP, title='Sentiment Over Time', markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No valid dates found for Sentiment Over Time chart.")
    else:
        st.info("No timeline data (date/time column) available for Sentiment Over Time chart.")

def generate_sentiment_pie_chart(df):
    sentiment_counts = df['sentiment_label'].str.upper().value_counts().reset_index()
    sentiment_counts.columns = ['Sentiment', 'Count']
    fig = px.pie(sentiment_counts, names='Sentiment', values='Count', color='Sentiment',
                 color_discrete_map=COLOR_MAP, title='Sentiment Share')
    st.plotly_chart(fig, use_container_width=True)

def generate_keyword_frequency_chart(freq_data):
    if not freq_data:
        st.info("No keywords available.")
        return
    df_kw = pd.DataFrame(freq_data, columns=['Keyword', 'Frequency'])
    fig = px.bar(df_kw, x='Frequency', y='Keyword', orientation='h', title='Top 10 Keywords',
                 color_discrete_sequence=['#17a2b8'])
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

def generate_wordcloud(text_data):
    if not text_data.strip():
        st.info("No text available for Word Cloud.")
        return
    wordcloud = WordCloud(width=800, height=400, background_color='white', colormap='viridis', max_words=100).generate(text_data)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    st.markdown("##### Word Cloud")
    st.pyplot(fig)
