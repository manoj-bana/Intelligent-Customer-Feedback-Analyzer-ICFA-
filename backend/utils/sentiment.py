import re
import os
import joblib
from collections import Counter
from typing import List, Dict, Any, Tuple

# Common English stop words (Comprehensive set)
_ENGLISH_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at", 
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't", "cannot", "could", 
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for", 
    "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", 
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", 
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", 
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", 
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", 
    "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", 
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", 
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", 
    "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", 
    "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", 
    "yourself", "yourselves", "than", "then", "thus", "onto", "upon", "into"
}

# Domain-specific and noise words to exclude from keyword extraction
STOP_WORDS = {
    "product", "products", "item", "items", "thing", "things",
    "good", "great", "nice", "fine", "okay", "also", "well", "just", 
    "really", "very", "much", "way", "even", "still", "first", "last", 
    "little", "lot", "many", "every", "make", "made", "work", "works", "working",
    "back", "give", "given", "come", "came", "look", "looks", "using", "used", "use",
    "feel", "felt", "put", "take", "run", "keep", "went", "day", "days", "time", 
    "never", "always", "since", "now", "can", "will", "need", "want", "know", "think", 
    "may", "bit", "br", "http", "https", "www", "com", "href", "src", "like", "love",
    "really", "quite", "actually", "probably", "possibly", "usually", "often", "always",
    "someone", "something", "anybody", "anything", "some", "many", "most", "each", "every"
}

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_sia = SentimentIntensityAnalyzer()
_STOP_WORDS = {w.lower() for w in (_ENGLISH_STOP_WORDS | STOP_WORDS)}

# --- Supervised Model Globals ---
_sentiment_model = None
_vectorizer = None
MODEL_PATH = "ml/sentiment_model.pkl"
VECT_PATH = "ml/vectorizer.pkl"

def _get_resources():
    """Lazy loader for sentiment analysis resources."""
    return _sia, _STOP_WORDS

def load_sentiment_model():
    """Loads the supervised ML model if it exists."""
    global _sentiment_model, _vectorizer
    if _sentiment_model is None:
        if os.path.exists(MODEL_PATH) and os.path.exists(VECT_PATH):
            try:
                _sentiment_model = joblib.load(MODEL_PATH)
                _vectorizer = joblib.load(VECT_PATH)
            except Exception:
                pass
    return _sentiment_model, _vectorizer

def _clean_text_for_keywords(text: str) -> str:
    """
    Standard cleaning pipeline for keyword extraction: 
    HTML removal, URL filtering, noise stripping.
    """
    # Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', str(text))
    # Remove URLs
    cleaned = re.sub(r'https?://\S+|www\.\S+', ' ', cleaned)
    # Remove everything except letters and spaces
    cleaned = re.sub(r'[^a-zA-Z\s]', ' ', cleaned).lower()
    return cleaned

def clean_text_v2(text: str) -> str:
    """
    Enhanced cleaning pipeline for supervised training.
    Removes HTML, URLs, punctuation, and filters stop words.
    """
    try:
        if not text or not isinstance(text, str):
            return ""
        
        # 1. HTML & URL removal
        cleaned = re.sub(r'<[^>]+>', ' ', text)
        cleaned = re.sub(r'https?://\S+|www\.\S+', ' ', cleaned)
        
        # 2. Noise & Number removal
        cleaned = re.sub(r'[^a-zA-Z\s]', ' ', cleaned).lower()
        
        # 3. Word-level filtering (Stop words + Short words)
        words = cleaned.split()
        filtered = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
        
        return " ".join(filtered)
    except Exception:
        return str(text).lower()

def _clean_text_for_sentiment(text: str) -> str:
    """
    Standard text cleaning for sentiment analysis.
    """
    return str(text).lower() if text else ""

def analyze_sentiment(text: str, config=None) -> dict:
    """
    Analyzes the sentiment of a given string using the VADER model.
    Supports custom thresholds and labels from a config object.
    """
    # 1. Load config values (with defaults)
    pos_thresh = config.pos_threshold if config and hasattr(config, "pos_threshold") else 0.05
    neg_thresh = config.neg_threshold if config and hasattr(config, "neg_threshold") else -0.05
    pos_lbl = config.pos_label if config and hasattr(config, "pos_label") else "Positive"
    neg_lbl = config.neg_label if config and hasattr(config, "neg_label") else "Negative"
    neu_lbl = config.neu_label if config and hasattr(config, "neu_label") else "Neutral"
    
    try:
        if not text or str(text).strip() == "":
            return {"label": neu_lbl, "score": 0.5}
            
        cleaned_text = _clean_text_for_sentiment(text)
        sia, _ = _get_resources()
        scores = sia.polarity_scores(cleaned_text)
        comp = scores["compound"]
        
        if comp >= pos_thresh: label = pos_lbl
        elif comp <= neg_thresh: label = neg_lbl
        else: label = neu_lbl
        
        return {
            "label": label, 
            "score": round((comp + 1.0) / 2.0, 3)
        }
    except Exception:
        return {"label": neu_lbl, "score": 0.5}

def analyze_sentiment_label_score(text: str) -> tuple[str, float]:
    """
    Convenience wrapper for analyze_sentiment that returns flat tuple.
    """
    res = analyze_sentiment(text if isinstance(text, str) else "")
    return res["label"], res["score"]

def extract_keywords_frequency(texts: list, top_n: int = 15) -> list:
    """
    Extracts the most frequent keywords from a list of texts, excluding stop words.
    """
    all_words = []
    _, stop_words = _get_resources()
    
    for text in texts:
        cleaned = _clean_text_for_keywords(text)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', cleaned)
        all_words.extend([w.strip() for w in words if w.strip() not in stop_words])
        
    counter = Counter(all_words)
    return [
        {"word": w, "count": c, "method": "frequency"} 
        for w, c in counter.most_common(top_n)
    ]

def extract_keywords_tfidf(texts: list, top_n: int = 15) -> list:
    """
    Extracts high-score keywords from a list of texts using TF-IDF analysis.
    """
    if len(texts) < 2:
        return extract_keywords_frequency(texts, top_n)
        
    cleaned_texts = [
        re.sub(r'\s+', ' ', _clean_text_for_keywords(t)).strip()
        for t in texts
    ]
    
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        _, stop_words_list = _get_resources()
        vectorizer = TfidfVectorizer(
            stop_words=list(stop_words_list), 
            max_features=1000, 
            token_pattern=r'\b[a-zA-Z]{4,}\b', 
            min_df=2, 
            max_df=0.85
        )
        tfidf_matrix = vectorizer.fit_transform(cleaned_texts)
        feature_names = vectorizer.get_feature_names_out()
        avg_scores = tfidf_matrix.mean(axis=0).A1
        
        word_scores = sorted(
            zip(feature_names, avg_scores), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        _, stop_words = _get_resources()
        final_keywords = [
            (w.strip(), s) for w, s in word_scores 
            if w.strip() not in stop_words
        ][:top_n]
        
        return [
            {"word": w, "score": round(float(s), 4), "method": "tfidf"} 
            for w, s in final_keywords
        ]
    except Exception:
        return extract_keywords_frequency(texts, top_n)

def batch_analyze_sentiment(texts: List[str], config=None) -> List[Dict[str, Any]]:
    """
    Optimized batch sentiment analysis.
    Tries supervised ML model first, falls back to VADER.
    """
    pos_lbl = getattr(config, "pos_label", "Positive")
    neg_lbl = getattr(config, "neg_label", "Negative")
    neu_lbl = getattr(config, "neu_label", "Neutral")
    
    model, vectorizer = load_sentiment_model()
    results = []

    # 1. Try Supervised ML
    if model and vectorizer:
        try:
            cleaned = [clean_text_v2(t) for t in texts]
            X_vec = vectorizer.transform(cleaned)
            preds = model.predict(X_vec)
            probs = model.predict_proba(X_vec)
            
            label_map = {0: neg_lbl, 1: neu_lbl, 2: pos_lbl}
            for i, p in enumerate(preds):
                # Score = (Prob[Pos] - Prob[Neg] + 1) / 2
                score = round((probs[i][2] - probs[i][0] + 1.0) / 2.0, 3)
                results.append({"label": label_map.get(p, neu_lbl), "score": score})
            return results
        except Exception:
            pass # Fallback to VADER

    # 2. VADER Fallback
    sia, _ = _get_resources()
    pos_thresh = getattr(config, "pos_threshold", 0.05)
    neg_thresh = getattr(config, "neg_threshold", -0.05)
    
    for text in texts:
        if not text or str(text).strip() == "":
            results.append({"label": neu_lbl, "score": 0.5})
            continue
            
        cleaned = str(text).lower()
        scores = sia.polarity_scores(cleaned)
        comp = scores["compound"]
        
        # Keyword boosters if in config
        boosters = getattr(config, "keyword_boosters", "")
        if boosters:
            for kw in boosters.split(","):
                if kw.strip().lower() in cleaned:
                    comp += 0.1

        if comp >= pos_thresh: label = pos_lbl
        elif comp <= neg_thresh: label = neg_lbl
        else: label = neu_lbl
        
        results.append({
            "label": label, 
            "score": round((comp + 1.0) / 2.0, 3)
        })
    return results



