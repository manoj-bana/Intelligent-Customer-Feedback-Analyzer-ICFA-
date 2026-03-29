"""
Tests for sentiment analysis engine: VADER scoring, keyword extraction, text cleaning.
"""
from backend.utils.sentiment import (
    analyze_sentiment,
    extract_keywords_frequency,
    extract_keywords_tfidf,
    _clean_text_for_keywords,
    STOP_WORDS,
)


# ─── VADER SENTIMENT ───

def test_positive_sentiment():
    result = analyze_sentiment("I absolutely love this product! Amazing experience!")
    assert result["label"] == "POSITIVE"
    assert result["score"] > 0.5


def test_negative_sentiment():
    result = analyze_sentiment("Terrible product. Worst purchase ever. Very disappointed.")
    assert result["label"] == "NEGATIVE"
    assert result["score"] < 0.5


def test_neutral_sentiment():
    result = analyze_sentiment("The package arrived on Tuesday.")
    assert result["label"] == "NEUTRAL"


def test_empty_text_returns_neutral():
    result = analyze_sentiment("")
    assert result["label"] == "NEUTRAL"
    assert result["score"] == 0.5


def test_none_text_returns_neutral():
    result = analyze_sentiment(None)
    assert result["label"] == "NEUTRAL"


def test_score_is_normalized():
    result = analyze_sentiment("Great!")
    assert 0.0 <= result["score"] <= 1.0


# ─── TEXT CLEANING ───

def test_clean_strips_html():
    cleaned = _clean_text_for_keywords("Hello <br /> world <b>bold</b>")
    assert "<" not in cleaned
    assert "br" not in cleaned


def test_clean_strips_urls():
    cleaned = _clean_text_for_keywords("Check https://example.com for details")
    assert "https" not in cleaned
    assert "example" not in cleaned


def test_clean_strips_numbers():
    cleaned = _clean_text_for_keywords("Product 12345 is great")
    assert "12345" not in cleaned


# ─── KEYWORD EXTRACTION ───

def test_frequency_keywords_returns_list():
    texts = [
        "amazing quality fabric, truly amazing",
        "the fabric quality is outstanding",
        "quality fabric design is perfect"
    ]
    result = extract_keywords_frequency(texts, top_n=5)
    assert isinstance(result, list)
    assert len(result) > 0
    assert all("word" in kw and "count" in kw for kw in result)


def test_frequency_keywords_excludes_stopwords():
    texts = ["the product is good and the item is nice"] * 5
    result = extract_keywords_frequency(texts, top_n=10)
    words = [kw["word"] for kw in result]
    for sw in ["the", "is", "and", "product", "good", "nice", "item"]:
        assert sw not in words, f"Stop word '{sw}' should be filtered but was found"


def test_tfidf_keywords_returns_list():
    texts = [
        "amazing quality fabric design",
        "the fabric quality is outstanding",
        "quality fabric design is perfect",
        "design and fabric are key features",
    ]
    result = extract_keywords_tfidf(texts, top_n=5)
    assert isinstance(result, list)
    assert len(result) > 0
    assert all("word" in kw and "score" in kw for kw in result)


def test_tfidf_fallback_on_single_text():
    """TF-IDF needs 2+ docs; should fallback to frequency with 1 doc."""
    result = extract_keywords_tfidf(["amazing quality fabric"], top_n=3)
    assert isinstance(result, list)
    assert all(kw["method"] == "frequency" for kw in result)


def test_domain_stopwords_populated():
    assert "product" in STOP_WORDS
    assert "great" in STOP_WORDS
    assert "br" in STOP_WORDS
