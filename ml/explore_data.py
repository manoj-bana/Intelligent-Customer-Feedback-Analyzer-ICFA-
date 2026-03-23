"""
Day 1 / Day 2 - Person 4
Explore the churn dataset before building the model.

Run: python ml/explore_data.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import re
try:
    from nltk.stem import PorterStemmer, WordNetLemmatizer
except Exception:
    PorterStemmer, WordNetLemmatizer = None, None

DATA_PATH = "ml/sample_data/churn_data.csv"
OUTPUT_PATH = "data/cleaned_feedback.csv"
TEXT_OUTPUT_PATH = "data/cleaned_text.csv"
 
df = pd.read_csv(DATA_PATH)

print("=" * 50)
print("STEP 1: Raw Data Info")
print("=" * 50)
print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n")
print("Columns:")
for col in df.columns:
    print(f"  - {col} ({df[col].dtype})")

print(f"\nMissing values:\n{df.isnull().sum()[df.isnull().sum() > 0]}")

# Clean
before_rows = df.shape[0]
df = df.drop_duplicates()
print(f"Duplicates removed: {before_rows - df.shape[0]}")

def normalize_text(x):
    x = str(x).lower()
    x = re.sub(r"[^\w\s]", "", x)  # remove punctuation
    return re.sub(r"\s+", " ", x).strip()

text_cols = df.select_dtypes(include="object").columns
df[text_cols] = df[text_cols].fillna("")
for col in text_cols:
    df[col] = df[col].apply(normalize_text)

df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
df = df.dropna(subset=["TotalCharges"])
df["Churn"] = df["Churn"].map({"yes": 1, "no": 0})

# Phase 2: text preprocessing
STOPWORDS = {
    "a", "an", "the", "and", "or", "is", "are", "was", "were", "to", "of", "in",
    "on", "for", "with", "this", "that", "it", "be", "as", "at", "by", "from"
}
stemmer = PorterStemmer() if PorterStemmer else None
lemmatizer = WordNetLemmatizer() if WordNetLemmatizer else None

def preprocess_text(x):
    tokens = re.findall(r"\b[a-z]+\b", str(x).lower())      # tokenization
    tokens = [t for t in tokens if t not in STOPWORDS]      # stopword removal
    if stemmer:
        tokens = [stemmer.stem(t) for t in tokens]          # stemming
    if lemmatizer:
        try:
            tokens = [lemmatizer.lemmatize(t) for t in tokens]  # lemmatization
        except LookupError:
            pass
    return " ".join(tokens)

text_candidates = ["feedback", "customer_feedback", "review", "comment", "text"]
text_col = next((c for c in text_candidates if c in df.columns), None)
if text_col:
    df["cleaned_text"] = df[text_col].fillna("").apply(preprocess_text)
    print(f"Text column used for preprocessing: {text_col}")
else:
    print("No dedicated text column found; skipped cleaned_text generation.")

print("\n" + "=" * 50)
print("STEP 2: After Cleaning")
print("=" * 50)
print(f"Shape after clean: {df.shape}")
print(f"Churn = 1 (leaves): {df['Churn'].sum()}")
print(f"Churn = 0 (stays):  {(df['Churn'] == 0).sum()}")
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)
print(f"Cleaned data saved to {OUTPUT_PATH}")
if "cleaned_text" in df.columns:
    df[["cleaned_text"]].to_csv(TEXT_OUTPUT_PATH, index=False)
    print(f"Cleaned text saved to {TEXT_OUTPUT_PATH}")

print("\n" + "=" * 50)
print("STEP 3: Key Patterns")
print("=" * 50)
print("Avg tenure (0=stays, 1=leaves):")
print(df.groupby("Churn")["tenure"].mean())
print("\nAvg monthly charges:")
print(df.groupby("Churn")["MonthlyCharges"].mean())
print("\nChurn rate by contract type:")
print(df.groupby("Contract")["Churn"].mean().sort_values(ascending=False))

# Charts
os.makedirs("ml/charts", exist_ok=True)
fig, axes = plt.subplots(1, 3, figsize=(15, 4))

df.groupby("Contract")["Churn"].mean().plot(
    kind="bar", ax=axes[0], color=["#4CAF50", "#FF9800", "#F44336"]
)
axes[0].set_title("Churn Rate by Contract Type")
axes[0].set_ylabel("Churn Rate")

df[df["Churn"] == 1]["MonthlyCharges"].hist(ax=axes[1], color="#F44336", alpha=0.7, label="Churned")
df[df["Churn"] == 0]["MonthlyCharges"].hist(ax=axes[1], color="#4CAF50", alpha=0.7, label="Stayed")
axes[1].set_title("Monthly Charges: Churned vs Stayed")
axes[1].legend()

df[df["Churn"] == 1]["tenure"].hist(ax=axes[2], color="#F44336", alpha=0.7, label="Churned")
df[df["Churn"] == 0]["tenure"].hist(ax=axes[2], color="#4CAF50", alpha=0.7, label="Stayed")
axes[2].set_title("Tenure: Churned vs Stayed")
axes[2].legend()

plt.tight_layout()
plt.savefig("ml/charts/eda_charts.png")
print("\nCharts saved to ml/charts/eda_charts.png")
plt.show()
