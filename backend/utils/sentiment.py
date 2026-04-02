import re
from collections import Counter
 
# Global cache for lazy loading heavy resources
_resources = {"sia": None, "stop_words": None}
 
# Common English stop words (no NLTK download required)
_ENGLISH_STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
    "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an",
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of",
    "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "s", "t", "just",
    "don", "should", "now", "d", "ll", "m", "o", "re", "ve", "y", "ain",
    "aren", "couldn", "didn", "doesn", "hadn", "hasn", "haven", "isn", "ma",
    "mightn", "mustn", "needn", "shan", "shouldn", "wasn", "weren", "won", "wouldn",
}
 
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
    Lazy loader for sentiment analysis resources.
    Uses vaderSentiment (standalone package, no NLTK downloads needed).
    """
    if _resources["sia"] is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _resources["sia"] = SentimentIntensityAnalyzer()
        _resources["stop_words"] = _ENGLISH_STOP_WORDS | STOP_WORDS
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