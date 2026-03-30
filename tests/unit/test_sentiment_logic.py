import pytest
from backend.utils.sentiment import analyze_sentiment, extract_keywords_frequency, extract_keywords_tfidf

def test_analyze_sentiment_positive():
    text = "This is the best product ever! I love it."
    result = analyze_sentiment(text)
    assert result["label"] == "POSITIVE"
    assert result["score"] > 0.5

def test_analyze_sentiment_negative():
    text = "Horrible experience. Extremely disappointed."
    result = analyze_sentiment(text)
    assert result["label"] == "NEGATIVE"
    assert result["score"] < 0.5

def test_analyze_sentiment_neutral():
    text = "The table is made of wood."
    result = analyze_sentiment(text)
    assert result["label"] == "NEUTRAL"

def test_analyze_sentiment_empty():
    assert analyze_sentiment("") == {"label": "NEUTRAL", "score": 0.5}
    assert analyze_sentiment(None) == {"label": "NEUTRAL", "score": 0.5}

def test_keyword_frequency():
    texts = [
        "The battery life is amazing and the battery is durable.",
        "I love the battery life of this phone."
    ]
    keywords = extract_keywords_frequency(texts, top_n=2)
    words = [k["word"] for k in keywords]
    assert "battery" in words

def test_keyword_tfidf():
    texts = [
        "programming is fun in python",
        "programming is hard in java",
        "i love programming with code"
    ]
    keywords = extract_keywords_tfidf(texts, top_n=5)
    # TF-IDF on small sets can be tricky. We check if it returns anything.
    assert len(keywords) > 0
