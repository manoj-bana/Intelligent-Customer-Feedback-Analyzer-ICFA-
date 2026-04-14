from typing import List, Dict, Any
from backend.utils.sentiment import (
    batch_analyze_sentiment as _batch_analyze,
    extract_keywords_frequency as _get_freq_kw,
    extract_keywords_tfidf as _get_tfidf_kw
)

def batch_analyze_sentiment(texts: List[str], config: Any = None) -> List[Dict[str, Any]]:
    """
    Main entry point for batch sentiment analysis.
    Delegates to the consolidated robust implementation in utils.
    """
    return _batch_analyze(texts, config=config)

def extract_keywords_frequency(texts: List[str], top_n: int = 15) -> List[Dict[str, Any]]:
    """Extracts frequent keywords."""
    return _get_freq_kw(texts, top_n)

def extract_keywords_tfidf(texts: List[str], top_n: int = 15) -> List[Dict[str, Any]]:
    """Extracts TF-IDF keywords."""
    return _get_tfidf_kw(texts, top_n)
