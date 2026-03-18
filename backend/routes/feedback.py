from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io
import base64
from backend.utils.sentiment import (
    analyze_sentiment,
    extract_keywords_frequency,
    extract_keywords_tfidf,
    add_sentiment_columns,
)
from backend.database.db import SessionLocal
from backend.database.models import Feedback

router = APIRouter()


@router.post("/analyze")
async def analyze_feedback(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {e}")

    # Auto-detect text column
    text_col = None
    for col in df.columns:
        if any(k in col.lower() for k in ["review", "feedback", "comment", "text"]):
            text_col = col
            break
    if not text_col:
        text_cols = df.select_dtypes(include="object").columns
        if len(text_cols) == 0:
            raise HTTPException(status_code=400, detail="No text column found in CSV")
        text_col = text_cols[0]

    # Analyze sentiment for each review (cap at 50 for speed)
    reviews = df[text_col].dropna().tolist()[:50]
    results = []
    for review in reviews:
        sentiment = analyze_sentiment(str(review))
        results.append({"review": str(review), **sentiment})

    # ── Phase 4: Keyword Extraction (both methods) ──
    review_texts = [r["review"] for r in results]
    freq_keywords  = extract_keywords_frequency(review_texts, top_n=15)
    tfidf_keywords = extract_keywords_tfidf(review_texts, top_n=15)

    # ── Phase 3: Store results in new columns on the original DataFrame ──
    # Build a small DataFrame from the analyzed rows and add sentiment columns
    analyzed_df = df[df[text_col].notna()].head(50).copy().reset_index(drop=True)
    analyzed_df["SentimentLabel"] = [r["label"] for r in results]
    analyzed_df["SentimentScore"] = [r["score"] for r in results]

    # Encode enriched CSV as base64 so frontend can offer a download button
    csv_bytes  = analyzed_df.to_csv(index=False).encode("utf-8")
    csv_base64 = base64.b64encode(csv_bytes).decode("utf-8")

    # Count labels
    positive = sum(1 for r in results if r["label"] == "POSITIVE")
    negative = sum(1 for r in results if r["label"] == "NEGATIVE")
    neutral  = sum(1 for r in results if r["label"] == "NEUTRAL")

    # Save to DB
    db = SessionLocal()
    for r in results:
        db.add(Feedback(user_id=1, text=r["review"], sentiment=r["label"]))
    db.commit()
    db.close()

    return {
        "total":           len(results),
        "positive":        positive,
        "negative":        negative,
        "neutral":         neutral,
        "results":         results,
        "keywords":        freq_keywords,   # frequency (kept for backward compat)
        "freq_keywords":   freq_keywords,   # Phase 4 – frequency count
        "tfidf_keywords":  tfidf_keywords,  # Phase 4 – TF-IDF
        "enriched_csv":    csv_base64,      # Phase 3 – download with new columns
    }


@router.get("/test")
def test():
    return {"message": "Feedback route working!"}
