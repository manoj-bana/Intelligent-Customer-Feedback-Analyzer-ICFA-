from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io
from backend.utils.sentiment import analyze_sentiment, extract_keywords
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

    reviews = df[text_col].dropna().tolist()[:50]  
    results = []
    for review in reviews:
        sentiment = analyze_sentiment(str(review))
        results.append({"review": str(review), **sentiment})

    keywords = extract_keywords([r["review"] for r in results])

    positive = sum(1 for r in results if r["label"] == "POSITIVE")
    negative = sum(1 for r in results if r["label"] == "NEGATIVE")
    neutral = sum(1 for r in results if r["label"] == "NEUTRAL")

    db = SessionLocal()

    for r in results:
        new_feedback = Feedback(
            user_id=1,
            text=r["review"],
            sentiment=r["label"]
        )
        db.add(new_feedback)
    db.commit()
    db.close()

    return {
        "total": len(results),
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "results": results,
        "keywords": keywords
    }

@router.get("/test")
def test():
    return {"message": "Feedback route working!"}
