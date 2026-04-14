import pandas as pd
import streamlit as st

def load_data(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        # Handle cases where feedback column could be named differently
        possible_text_cols = ['feedback_text', 'review', 'feedback', 'comment', 'text']
        text_col = next((col for col in possible_text_cols if col.lower() in [c.lower() for c in df.columns]), None)
        
        if not text_col:
            st.error("Missing required column for feedback text. Looking for one of: " + ", ".join(possible_text_cols))
            return None, None
            
        # Get actual column name from df
        actual_text_col = next(col for col in df.columns if col.lower() == text_col.lower())
        
        # Ensure 'feedback_text' is the standard column name going forward
        if actual_text_col != 'feedback_text':
            df.rename(columns={actual_text_col: 'feedback_text'}, inplace=True)
            
        df['feedback_text'] = df['feedback_text'].fillna("").astype(str)
        return df, actual_text_col
    except Exception as e:
        st.error(f"Invalid file format or error reading CSV: {e}")
        return None, None

def aggregate_user_data(df):
    """Aggregates per-user sentiment stats with rich analytics. Works with any column naming."""
    # Step 1: Find the user/customer ID column
    user_col = next((col for col in ['user_id', 'userid', 'user', 'customer_id', 'customerid', 'id'] if col.lower() in [c.lower() for c in df.columns]), None)
    if not user_col:
        user_col = next((c for c in df.columns if 'id' in c.lower()), None)
    
    if not user_col:
        return None
        
    actual_user_col = next(col for col in df.columns if col.lower() == user_col.lower())
    
    if 'sentiment_label' not in df.columns:
        return None
    
    # Step 2: Find the text column dynamically (handles 'Text', 'feedback_text', 'review', etc.)
    text_col = next((c for c in df.columns if c.lower() in ['feedback_text', 'review', 'text', 'feedback', 'comment']), None)
    if not text_col:
        # Fallback: use sentiment_label for counting
        text_col = 'sentiment_label'
    
    # Step 3: Check for score column (handles both 'score' and 'sentiment_score')
    score_col = next((c for c in df.columns if c.lower() in ['score', 'sentiment_score']), None)
    

        
    def get_dominant_sentiment(x):
        return x.mode()[0] if not x.mode().empty else "UNKNOWN"
    
    def count_positive(x):
        return (x.str.upper() == 'POSITIVE').sum()

    def count_negative(x):
        return (x.str.upper() == 'NEGATIVE').sum()

    def count_neutral(x):
        return (x.str.upper() == 'NEUTRAL').sum()
        
    def calc_churn_score(x):
        total = len(x)
        if total == 0:
            return 0.0
        negative_count = (x.str.upper() == 'NEGATIVE').sum()
        return round(negative_count / total, 2)
    
    agg_dict = {
        'Positive': ('sentiment_label', count_positive),
        'Negative': ('sentiment_label', count_negative),
        'Neutral': ('sentiment_label', count_neutral),
        'Dominant_Sentiment': ('sentiment_label', get_dominant_sentiment),
        'Churn_Risk': ('sentiment_label', calc_churn_score),
    }
    
    # Add average score if column exists
    if score_col:
        agg_dict['Avg_Score'] = (score_col, lambda x: round(x.mean(), 3))

    agg_df = df.groupby(actual_user_col).agg(**agg_dict).reset_index()
    
    rename_map = {
        actual_user_col: 'User ID',
        'Positive': '👍 Positive',
        'Negative': '👎 Negative',
        'Neutral': '😐 Neutral',
        'Dominant_Sentiment': 'Dominant Sentiment',
        'Churn_Risk': 'Churn Risk',
    }
    if score_col:
        rename_map['Avg_Score'] = 'Sentiment Score'
    
    agg_df.rename(columns=rename_map, inplace=True)
    
    return agg_df
