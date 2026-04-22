import re
import os
import joblib
import nltk
from collections import Counter
from typing import List, Dict, Any, Tuple
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# --- Standard NLTK Resources ---
try:
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    _STOP_WORDS = set(stopwords.words('english'))
    _lemmatizer = WordNetLemmatizer()
except Exception:
    # Minimal fallback only if NLTK is somehow broken
    _STOP_WORDS = {"a", "the", "is", "in", "it", "to", "and", "or"}
    _lemmatizer = None

DOMAIN_STOP_WORDS = {
    # Generic sentiment words (Noise for topic analysis)
    "good", "great", "best", "excellent", "amazing", "love", "like", "wonderful", "perfect",
    "bad", "terrible", "awful", "worst", "horrible", "okay", "fine", "nice", "better",
    # Filler and high-frequency noise
    "one", "would", "get", "got", "really", "also", "even", "still", "much", "many",
    "thing", "things", "way", "could", "should", "want", "know", "think", "br",
    # Technical/Domain noise
    "product", "products", "item", "items", "http", "https", "www", "com", "href", "src",
    "using", "used", "use", "make", "made", "work", "works", "working"
}
_STOP_WORDS |= DOMAIN_STOP_WORDS

def _get_nltk_resources():
    return _STOP_WORDS, _lemmatizer

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_sia = SentimentIntensityAnalyzer()
# (Redundant line removed here)

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
    Includes: HTML/URL removal, Negation handling, Lemmatization, and Stopword filtering.
    """
    try:
        if not text or not isinstance(text, str):
            return ""
        
        # 1. HTML & URL removal
        cleaned = re.sub(r'<[^>]+>', ' ', text)
        cleaned = re.sub(r'https?://\S+|www\.\S+', ' ', cleaned)
        
        # 2. Noise & Number removal (Preserve '!' for sentiment hint)
        cleaned = re.sub(r'[^a-zA-Z\s!]', ' ', cleaned).lower()
        
        # 3. Negation Handling (e.g., "not happy" -> "not_happy")
        negations = {"not", "no", "never", "n't", "cannot", "without", "hardly", "seldom"}
        words = cleaned.split()
        transformed = []
        skip_next = False
        
        for i in range(len(words)):
            if skip_next:
                skip_next = False
                continue
            
            if words[i] in negations and i + 1 < len(words):
                # Attach negation to next word
                transformed.append(f"{words[i]}_{words[i+1]}")
                skip_next = True
            else:
                transformed.append(words[i])
        
        # 4. Lemmatization & Stopword filtering
        filtered = []
        for w in transformed:
            if _lemmatizer:
                lemma = _lemmatizer.lemmatize(w)
            else:
                lemma = w
                
            # Filter stopwords
            if "_" in lemma or (lemma not in _STOP_WORDS and len(lemma) > 1) or lemma == "!":
                filtered.append(lemma)
        
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

def batch_analyze_sentiment(texts: list) -> list:
    """
    High-performance batch processor for sentiment labels and scores.
    """
    sia, _ = _get_resources()
    results = []
    for text in texts:
        if not text or str(text).strip() == "":
            results.append({"label": "NEUTRAL", "score": 0.5})
            continue
        comp = sia.polarity_scores(str(text).lower())["compound"]
        label = "POSITIVE" if comp >= 0.05 else ("NEGATIVE" if comp <= -0.05 else "NEUTRAL")
        results.append({"label": label, "score": round((comp + 1.0) / 2.0, 3)})
    return results

def extract_keywords_frequency(texts: list, top_n: int = 15) -> list:
    """
    Extracts the most frequent keywords from a list of texts, excluding stop words.
    """
    all_words = []
    _, stop_words = _get_resources()
    
    for text in texts:
        cleaned = _clean_text_for_keywords(text)
        # Updated regex to allow shorter words (2+ letters)
        words = re.findall(r'\b[a-zA-Z]{2,}\b', cleaned)
        all_words.extend([w.strip() for w in words if w.strip() not in stop_words])
        
    counter = Counter(all_words)
    results = []
    sia = SentimentIntensityAnalyzer() # Use VADER for individual word weighting
    
    for word, count in counter.most_common(top_n * 2): # Look at more candidates
        # Calculate sentiment weight: |compound| + 1.0 (multiplier)
        s_score = abs(sia.polarity_scores(word)["compound"])
        weighted_score = count * (1.0 + s_score * 2.0) # Boost polar words by up to 3x
        results.append({"word": word, "count": count, "score": round(weighted_score, 2), "method": "frequency_weighted"})
    
    # Sort by weighted score and return top_n
    return sorted(results, key=lambda x: x["score"], reverse=True)[:top_n]

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
            token_pattern=r'\b[a-zA-Z]{2,}\b', 
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

import re

def _apply_keyword_boosters(text: str, current_score: float, pos_str: str, neg_str: str) -> float:
    """Helper to adjust sentiment score based on separate pos/neg keywords."""
    if not pos_str and not neg_str:
        return current_score
    
    cleaned = str(text).lower()
    new_score = current_score
    
    def get_list(s):
        if not s: return []
        # Support comma and semicolon
        return [w.strip().lower() for w in re.split(r'[,;]', s) if w.strip()]

    # 1. Positive Boost (+0.2 per hit)
    for kw in get_list(pos_str):
        if re.search(rf"\b{re.escape(kw)}\b", cleaned):
            new_score += 0.20
            
    # 2. Negative Boost (-0.2 per hit)
    for kw in get_list(neg_str):
        if re.search(rf"\b{re.escape(kw)}\b", cleaned):
            new_score -= 0.20
    
    # Clip to -1.0 to 1.0 range
    return max(-1.0, min(1.0, new_score))

def batch_analyze_sentiment(texts: List[str], config=None) -> List[Dict[str, Any]]:
    """
    Optimized batch sentiment analysis.
    PRIORITY: Supervised ML -> Transformer -> VADER
    UNIFIED with Admin thresholds and separate Pos/Neg boosters.
    """
    results = []
    pos_lbl = getattr(config, "pos_label", "Positive")
    neg_lbl = getattr(config, "neg_label", "Negative")
    neu_lbl = getattr(config, "neu_label", "Neutral")
    pos_thresh = getattr(config, "pos_threshold", 0.05)
    neg_thresh = getattr(config, "neg_threshold", -0.05)
    
    pos_kw = getattr(config, "positive_keywords", "") or getattr(config, "keyword_boosters", "")
    neg_kw = getattr(config, "negative_keywords", "")

    # 1. Try Supervised ML
    model, vectorizer = load_sentiment_model()
    if model and vectorizer:
        try:
            cleaned = [clean_text_v2(t) for t in texts]
            X_vec = vectorizer.transform(cleaned)
            probs = model.predict_proba(X_vec)
            
            for i, p_row in enumerate(probs):
                base_score = p_row[2] - p_row[0]
                final_score = _apply_keyword_boosters(texts[i], base_score, pos_kw, neg_kw)
                
                if final_score >= pos_thresh: label = pos_lbl
                elif final_score <= neg_thresh: label = neg_lbl
                else: label = neu_lbl
                
                results.append({
                    "label": label, 
                    "score": round((final_score + 1.0) / 2.0, 3),
                    "method": "supervised_ml"
                })
            return results
        except Exception:
            pass

    # 2. Transformer
    use_trans = getattr(config, "use_transformer", os.environ.get("USE_TRANSFORMERS", "false").lower() == "true")
    if use_trans:
        trans_results = analyze_sentiment_transformer(texts)
        if trans_results and trans_results[0].get("label") != "ERROR":
            return trans_results

    # 3. VADER Fallback
    sia, _ = _get_resources()
    for text in texts:
        if not text or str(text).strip() == "":
            results.append({"label": neu_lbl, "score": 0.5})
            continue
            
        cleaned = str(text).lower()
        comp = sia.polarity_scores(cleaned)["compound"]
        final_score = _apply_keyword_boosters(text, comp, pos_kw, neg_kw)
        
        if final_score >= pos_thresh: label = pos_lbl
        elif final_score <= neg_thresh: label = neg_lbl
        else: label = neu_lbl
        
        results.append({
            "label": label, 
            "score": round((final_score + 1.0) / 2.0, 3),
            "method": "vader_fallback"
        })
    return results

# --- Transformer (Demo/Alternative) ---
_transformer_pipeline = None

def analyze_sentiment_transformer(texts: List[str]) -> List[Dict[str, Any]]:
    """
    Advanced sentiment analysis using HuggingFace Transformers.
    Caches the model in memory for production performance.
    """
    global _transformer_pipeline
    try:
        if _transformer_pipeline is None:
            from transformers import pipeline
            # Lazy load and cache the pipeline
            _transformer_pipeline = pipeline(
                "sentiment-analysis", 
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1 # Set to 0 if you have a GPU
            )
        
        # Process in batch
        raw_results = _transformer_pipeline(texts, truncation=True, batch_size=8)
        
        results = []
        for res in raw_results:
            # Map label to system labels
            label = res['label'].upper() # 'POSITIVE' or 'NEGATIVE'
            score = round(res['score'], 3)
            # If negative, we might want to scale score to 0-0.5 range for consistency if needed
            # but usually transformer score is confidence in the label.
            results.append({"label": label, "score": score, "method": "transformer"})
        return results
    except Exception as e:
        return [{"label": "ERROR", "score": 0.5, "error": str(e)}] * len(texts)



