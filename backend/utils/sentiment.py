from transformers import pipeline
import nltk
from collections import Counter
import re

nltk.download("stopwords", quiet=True)
from nltk.corpus import stopwords

print("Loading HuggingFace DistilBERT sentiment model...")
sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english"
)
print("Sentiment model ready!")

STOP_WORDS = set(stopwords.words("english"))


def analyze_sentiment(text: str) -> dict:
    """Returns label (POSITIVE/NEGATIVE/NEUTRAL) and confidence score."""
    try:
        result = sentiment_pipeline(text[:512])[0]
        label = result["label"]
        # Treat low-confidence results as NEUTRAL
        if result["score"] < 0.65:
            label = "NEUTRAL"
        return {"label": label, "score": round(result["score"], 3)}
    except Exception as e:
        print(f"Sentiment error: {e}")
        return {"label": "NEUTRAL", "score": 0.5}


def extract_keywords(texts: list, top_n: int = 15) -> list:
    """Extract most frequent meaningful words from a list of texts."""
    all_words = []
    for text in texts:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        words = [w for w in words if w not in STOP_WORDS]
        all_words.extend(words)
    counter = Counter(all_words)
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n)]

import pandas as pd

def analyze_sentiment_label_score(text: str) -> tuple[str, float]:

    res = analyze_sentiment(text if isinstance(text, str) else "")
    return res["label"], res["score"]

def classify_feedback_series(series: pd.Series) -> pd.DataFrame:

    labels = []
    scores = []
    for txt in series.fillna(""):
        label, score = analyze_sentiment_label_score(txt)
        labels.append(label)
        scores.append(score)
    return pd.DataFrame({"SentimentLabel": labels, "SentimentScore": scores})

def add_sentiment_columns(df: pd.DataFrame, text_col: str = "feedback") -> pd.DataFrame:

    if text_col not in df.columns:
        raise ValueError(
            f"Column '{text_col}' not found. Available columns: {list(df.columns)}"
        )
    sentiment_df = classify_feedback_series(df[text_col])
    df_out = df.copy()
    df_out["SentimentLabel"] = sentiment_df["SentimentLabel"]
    df_out["SentimentScore"] = sentiment_df["SentimentScore"]
    return df_out

def classify_feedback_file(
    input_path: str,
    text_col: str = "feedback",
    output_path: str | None = None
) -> str:

    # Load
    lower = input_path.lower()
    if lower.endswith(".csv"):
        df = pd.read_csv(input_path)
    elif lower.endswith(".xlsx"):
        df = pd.read_excel(input_path, engine="openpyxl")
    elif lower.endswith(".xls"):
        df = pd.read_excel(input_path, engine="xlrd")
    else:
        raise ValueError("Unsupported file type. Use .csv, .xlsx, or .xls")

    df_out = add_sentiment_columns(df, text_col=text_col)

    if output_path is None:
        stem = input_path.rsplit(".", 1)[0]
        output_path = f"{stem}_with_sentiment.csv"

    if output_path.lower().endswith(".csv"):
        df_out.to_csv(output_path, index=False)
    elif output_path.lower().endswith(".xlsx"):
        df_out.to_excel(output_path, index=False, engine="openpyxl")
    else:
        df_out.to_csv(output_path, index=False)

    return output_path

if __name__ == "__main__":
    sample = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "feedback": [
            "Absolutely love the product! Great experience.",
            "Terrible service. I'm very disappointed.",
            "It's okay, nothing special.",
            "Good features but the app crashes sometimes."
        ]
    })
    sample_with_sentiment = add_sentiment_columns(sample, text_col="feedback")
    print(sample_with_sentiment)
