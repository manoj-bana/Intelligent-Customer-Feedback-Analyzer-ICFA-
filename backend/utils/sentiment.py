import re
from collections import Counter

# Global cache for lazy loading heavy ML/NLTK resources
_resources = {"sia": None, "stop_words": None}

def _get_resources():
    """
    Lazy loader for NLTK and sentiment analysis resources.
    Ensures resources are only downloaded and initialized once.
    """
    if _resources["sia"] is None:
        import nltk
        from nltk.corpus import stopwords
        from nltk.sentiment import SentimentIntensityAnalyzer
        
        nltk.download("stopwords", quiet=True)
        nltk.download("vader_lexicon", quiet=True)
        
        _resources["sia"] = SentimentIntensityAnalyzer()
        _resources["stop_words"] = set(stopwords.words("english")) | {
            "product", "products", "item", "items", "thing", "things",
            "good", "great", "nice", "fine", "okay", "like", "love",
            "also", "well", "just", "get", "got", "one", "two", "use",
            "used", "using", "really", "very", "much", "way", "even",
            "would", "could", "still", "first", "last", "little", "lot",
            "many", "every", "make", "made", "work", "works", "working",
            "back", "give", "given", "come", "came", "look", "looks",
            "feel", "felt", "put", "take", "run", "keep", "went",
            "day", "days", "time", "never", "always", "since", "now",
            "can", "will", "need", "want", "know", "think", "may", "bit",
            "br", "http", "https", "www", "com", "href", "src",
            "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        }
    return _resources["sia"], _resources["stop_words"]

def analyze_sentiment(text: str) -> dict:
    """
    Analyzes the sentiment of a given string using the VADER model.
    Returns a dictionary with 'label' and 'score'.
    """
    try:
        if not text or str(text).strip() == "":
            return {"label": "NEUTRAL", "score": 0.5}
            
        sia, _ = _get_resources()
        scores = sia.polarity_scores(str(text))
        comp = scores["compound"]
        
        label = "POSITIVE" if comp >= 0.05 else ("NEGATIVE" if comp <= -0.05 else "NEUTRAL")
        return {
            "label": label, 
            "score": round((comp + 1.0) / 2.0, 3)
        }
    except Exception:
        return {"label": "NEUTRAL", "score": 0.5}

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
        cleaned = re.sub(r'<[^>]+>', ' ', str(text))
        cleaned = re.sub(r'https?://\S+|www\.\S+', ' ', cleaned)
        cleaned = re.sub(r'[^a-zA-Z\s]', ' ', cleaned).lower()
        words = re.findall(r'\b[a-zA-Z]{4,}\b', cleaned)
        all_words.extend([w for w in words if w not in stop_words])
        
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
        re.sub(
            r'\s+', ' ', 
            re.sub(
                r'[^a-zA-Z\s]', ' ', 
                re.sub(
                    r'https?://\S+|www\.\S+', ' ', 
                    re.sub(r'<[^>]+>', ' ', str(t))
                )
            )
        ).strip().lower() 
        for t in texts
    ]
    
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vectorizer = TfidfVectorizer(
            stop_words="english", 
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
            (w, s) for w, s in word_scores 
            if w not in stop_words
        ][:top_n]
        
        return [
            {"word": w, "score": round(float(s), 4), "method": "tfidf"} 
            for w, s in final_keywords
        ]
    except Exception:
        return extract_keywords_frequency(texts, top_n)
