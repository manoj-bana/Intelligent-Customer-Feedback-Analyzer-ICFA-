import re
from collections import Counter

# Global cache for lazy loading heavy ML/NLTK resources
_resources = {"sia": None, "stop_words": None}

# Domain-specific stop words to exclude from keyword extraction
STOP_WORDS = {
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
        _resources["stop_words"] = set(stopwords.words("english")) | STOP_WORDS
    return _resources["sia"], _resources["stop_words"]

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

from fuzzywuzzy import process

# High-impact sentiment words for fuzzy correction (derived from VADER's top valence scores)
SENTIMENT_LEXICON = [
    "excellent", "amazing", "great", "good", "happy", "love", "best", "awesome", "fantastic", "perfect",
    "helpful", "fast", "easy", "efficient", "recommend", "brilliant", "wonderful", "outstanding", "superb", "delighted",
    "terrible", "horrible", "awful", "bad", "hate", "worst", "expensive", "slow", "broken", "useless",
    "frustrated", "annoyed", "rude", "poor", "difficult", "failed", "waste", "missing", "unhelpful", "disappointed"
]

def _clean_text_for_sentiment(text: str) -> str:
    """
    Generalized cleaning with Fuzzy Lexicon Correction.
    Detects and fixes OCR typos for high-impact sentiment words.
    """
    if not text:
        return ""
        
    words = str(text).lower().split()
    corrected_words = []
    
    for word in words:
        # Only attempt fuzzy correction on words of a certain length to avoid false positives
        if len(word) >= 4:
            # Check if word is already a close match to something in our lexicon
            match, score = process.extractOne(word, SENTIMENT_LEXICON)
            if score >= 85: # High confidence threshold
                corrected_words.append(match)
                continue
        corrected_words.append(word)
        
    return " ".join(corrected_words)

def analyze_sentiment(text: str) -> dict:
    """
    Analyzes the sentiment of a given string using the VADER model.
    Returns a dictionary with 'label' and 'score'.
    """
    try:
        if not text or str(text).strip() == "":
            return {"label": "NEUTRAL", "score": 0.5}
            
        cleaned_text = _clean_text_for_sentiment(text)
        sia, _ = _get_resources()
        scores = sia.polarity_scores(cleaned_text)
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
        cleaned = _clean_text_for_keywords(text)
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
        re.sub(r'\s+', ' ', _clean_text_for_keywords(t)).strip()
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
