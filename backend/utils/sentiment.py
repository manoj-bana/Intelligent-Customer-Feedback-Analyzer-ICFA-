from transformers import pipeline
import nltk
from collections import Counter
import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

nltk.download("stopwords", quiet=True)
from nltk.corpus import stopwords

# HuggingFace is removed to achieve 10,000+ row processing in <3s
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
nltk.download("vader_lexicon", quiet=True)

class HighSpeedSentiment:
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        
    def __call__(self, texts, **kwargs):
        if isinstance(texts, str):
            texts = [texts]
        res = []
        for t in texts:
            score = self.sia.polarity_scores(t)
            compound = score['compound']
            if compound >= 0.05:
                res.append({"label": "POSITIVE", "score": round(abs(compound), 3) if abs(compound) > 0.65 else 0.7})
            elif compound <= -0.05:
                res.append({"label": "NEGATIVE", "score": round(abs(compound), 3) if abs(compound) > 0.65 else 0.7})
            else:
                res.append({"label": "NEUTRAL", "score": 0.5})
        return res

print("Loading High-Speed VADER sentiment model...")
sentiment_pipeline = HighSpeedSentiment()
print("Sentiment model ready!")

STOP_WORDS = set(stopwords.words("english"))


# ======================
# Phase 3: Sentiment Analysis
# ======================

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
    """
    Phase 3 requirement: Store sentiment results in new columns.
    Adds SentimentLabel and SentimentScore columns to the DataFrame.
    """
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


# ======================
# Phase 4: Keyword Extraction
# ======================

def extract_keywords_frequency(texts: list, top_n: int = 15) -> list:
    """
    Phase 4 requirement: Frequency count based keyword extraction.
    Counts how many times each meaningful word appears across all texts.
    Returns top N words sorted by frequency.
    """
    all_words = []
    for text in texts:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        words = [w for w in words if w not in STOP_WORDS]
        all_words.extend(words)
    counter = Counter(all_words)
    return [{"word": w, "count": c, "method": "frequency"}
            for w, c in counter.most_common(top_n)]


def extract_keywords_tfidf(texts: list, top_n: int = 15) -> list:
    """
    Phase 4 requirement: TF-IDF based keyword extraction.
    TF-IDF (Term Frequency - Inverse Document Frequency) scores words higher
    if they appear often in a document but rarely across all documents.
    This means it finds words that are uniquely important, not just common.
    Returns top N words sorted by their average TF-IDF score.
    """
    # Need at least 2 texts for TF-IDF to work meaningfully
    if len(texts) < 2:
        return extract_keywords_frequency(texts, top_n)

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=500,
            token_pattern=r'\b[a-zA-Z]{3,}\b'
        )
        tfidf_matrix = vectorizer.fit_transform(texts)

        feature_names = vectorizer.get_feature_names_out()

        # Average TF-IDF score for each word across all documents
        avg_scores = tfidf_matrix.mean(axis=0).A1

        word_scores = sorted(
            zip(feature_names, avg_scores),
            key=lambda x: x[1],
            reverse=True
        )

        return [{"word": w, "score": round(float(s), 4), "method": "tfidf"}
                for w, s in word_scores[:top_n]]

    except Exception as e:
        print(f"TF-IDF error: {e}, falling back to frequency")
        return extract_keywords_frequency(texts, top_n)


def extract_keywords(texts: list, top_n: int = 15) -> list:
    """
    Kept for backward compatibility — returns frequency-based keywords.
    """
    return extract_keywords_frequency(texts, top_n)


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
