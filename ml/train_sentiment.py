import os
import sys

# Add project root to path so 'backend' can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from backend.utils.sentiment import clean_text_v2

# Configuration
INPUT_DATA = "data/feedback_small.csv" # Default sample dataset
MODEL_OUT = "ml/sentiment_model.pkl"
VECT_OUT = "ml/vectorizer.pkl"

def train():
    print("🚀 Starting Supervised Sentiment Training...")
    
    if not os.path.exists(INPUT_DATA):
        print(f"❌ Error: Dataset {INPUT_DATA} not found.")
        return

    # 1. Load Data
    df = pd.read_csv(INPUT_DATA)
    
    # Auto-detect columns (find text and sentiment/score)
    text_col = next((c for c in df.columns if any(k in c.lower() for k in ["text", "review", "feedback"])), None)
    score_col = next((c for c in df.columns if any(k in c.lower() for k in ["score", "rating", "sentiment", "label"])), None)
    
    if not text_col or not score_col:
        print(f"❌ Error: Required columns not found. Detected: {df.columns.tolist()}")
        return

    print(f"📦 Using columns: Text='{text_col}', Label='{score_col}'")
    df = df[[text_col, score_col]].dropna()

    # 2. Label Mapping (Score 1-5 to 0-2)
    def map_labels(val):
        try:
            v = int(val)
            if v <= 2: return 0 # Negative
            if v == 3: return 1 # Neutral
            return 2            # Positive
        except:
            # Handle string labels if present
            s = str(val).upper()
            if "NEG" in s: return 0
            if "NEU" in s: return 1
            return 2

    df['label'] = df[score_col].apply(map_labels)
    
    # 3. Text Cleaning (Using stemming logic from sentiment2)
    print("🧹 Cleaning and Stemming text...")
    df['cleaned'] = df[text_col].apply(clean_text_v2)

    # 4. Split and Vectorize
    X_train, X_test, y_train, y_test = train_test_split(
        df['cleaned'], df['label'], test_size=0.2, random_state=42, stratify=df['label']
    )

    print("🔢 Vectorizing with TF-IDF...")
    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1,2))
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # 5. Train Model
    print("🛠️ Training Logistic Regression (Balanced)...")
    model = LogisticRegression(max_iter=500, class_weight='balanced')
    model.fit(X_train_vec, y_train)

    # 6. Evaluate
    y_pred = model.predict(X_test_vec)
    print(f"\n✅ Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Negative', 'Neutral', 'Positive']))

    # 7. Persistence
    os.makedirs("ml", exist_ok=True)
    joblib.dump(model, MODEL_OUT)
    joblib.dump(vectorizer, VECT_OUT)
    print(f"\n💾 Model saved to {MODEL_OUT}")
    print(f"💾 Vectorizer saved to {VECT_OUT}")

if __name__ == "__main__":
    train()
