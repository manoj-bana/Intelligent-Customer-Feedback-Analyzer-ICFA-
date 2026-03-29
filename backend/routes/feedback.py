from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import pandas as pd
import io
import base64
from backend.utils.sentiment import (
    analyze_sentiment,
    extract_keywords_frequency,
    extract_keywords_tfidf,
    add_sentiment_columns,
    sentiment_pipeline,
)
from backend.database.db import SessionLocal
from backend.database.models import Feedback

import os
import uuid
import shutil

router = APIRouter()

# 100 MB Limit for file upload to prevent server crash
MAX_FILE_SIZE = 100 * 1024 * 1024

# In-memory dictionary to store background job status and results
# In a real-world app with multiple workers, usually replaced by Redis or a DB table
feedback_jobs = {}

def process_feedback_background(job_id: str, file_path: str):
    """
    Background worker function that reads the saved CSV file in chunks
    and processes it without blocking the main API thread.
    """
    # Chunk processing variables
    total = 0
    positive = 0
    negative = 0
    neutral = 0
    results_sample = [] # Keep sample for API response
    text_col = None
    
    csv_base64 = ""
    freq_keywords = []
    tfidf_keywords = []
    first_chunk = True

    try:
        db = SessionLocal()
        
        # We chunk file 500 rows at a time for memory safety
        for chunk in pd.read_csv(file_path, chunksize=500):
            # 1. Detect column
            if not text_col:
                for col in chunk.columns:
                    if any(k in col.lower() for k in ["review", "feedback", "comment", "text"]):
                        text_col = col
                        break
                if not text_col:
                    text_cols = chunk.select_dtypes(include="object").columns
                    if len(text_cols) == 0:
                        raise ValueError("No text column found in CSV")
                    text_col = text_cols[0]
                    
            # Process rows
            reviews = chunk[text_col].dropna().astype(str).tolist()
            
            # Fast Batch Prediction
            try:
                truncated_reviews = [r[:512] for r in reviews]
                batch_results = sentiment_pipeline(truncated_reviews, batch_size=128)
            except Exception as e:
                print(f"Batch prediction error: {e}")
                batch_results = [{"label": "NEUTRAL", "score": 0.5}] * len(reviews)
            
            chunk_results = []
            db_entries = []
            
            for review, res in zip(reviews, batch_results):
                label = res["label"]
                if res["score"] < 0.65:
                    label = "NEUTRAL"
                    
                sentiment = {"label": label, "score": round(res["score"], 3)}
                res_obj = {"review": review, **sentiment}
                chunk_results.append(res_obj)
                
                # Update aggregated stats
                if label == "POSITIVE": positive += 1
                elif label == "NEGATIVE": negative += 1
                elif label == "NEUTRAL": neutral += 1
                total += 1
                
                db_entries.append(Feedback(user_id=1, text=review, sentiment=label))
                
            db.add_all(db_entries)
            db.commit()
            feedback_jobs[job_id]["progress"] = f"Processed {total} reviews so far..."
            
            # Legacy support: keep a sample of max 50 rows from the first chunk 
            if first_chunk and len(chunk_results) > 0:
                results_sample = chunk_results[:50]
                sample_reviews = [r["review"] for r in results_sample]
                
                freq_keywords = extract_keywords_frequency(sample_reviews, top_n=15)
                tfidf_keywords = extract_keywords_tfidf(sample_reviews, top_n=15)
                
                # Base64 encoded CSV preview for the sample
                analyzed_df = chunk.head(len(results_sample)).copy().reset_index(drop=True)
                analyzed_df["SentimentLabel"] = [r["label"] for r in results_sample]
                analyzed_df["SentimentScore"] = [r["score"] for r in results_sample]
                
                csv_bytes  = analyzed_df.to_csv(index=False).encode("utf-8")
                csv_base64 = base64.b64encode(csv_bytes).decode("utf-8")
                
                first_chunk = False

        db.close()
        
        # Update job status successfully
        feedback_jobs[job_id]["status"] = "completed"
        feedback_jobs[job_id]["result"] = {
            "total":           total,
            "positive":        positive,
            "negative":        negative,
            "neutral":         neutral,
            "results":         results_sample,
            "keywords":        freq_keywords,
            "freq_keywords":   freq_keywords,
            "tfidf_keywords":  tfidf_keywords,
            "enriched_csv":    csv_base64,
        }
        
    except Exception as e:
        feedback_jobs[job_id]["status"] = "failed"
        feedback_jobs[job_id]["error"] = str(e)
    
    # File is now kept in uploads/ as per user request for verification

@router.post("/analyze")
async def analyze_feedback(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    file_id = str(uuid.uuid4())
    file_path = os.path.join("uploads", f"{file_id}_{file.filename}")
    
    # Safely stream and save the file in chunks while enforcing a max size limit
    try:
        size = 0
        with open(file_path, "wb") as buffer:
            while content := await file.read(1024 * 1024):  # read 1MB chunks
                size += len(content)
                if size > MAX_FILE_SIZE:
                    if os.path.exists(file_path): os.remove(file_path)
                    raise HTTPException(status_code=413, detail=f"File exceeds the 100MB limit.")
                buffer.write(content)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to save file securely: {e}")

    # Start Processing in the background
    job_id = str(uuid.uuid4())
    feedback_jobs[job_id] = {"status": "processing"}
    background_tasks.add_task(process_feedback_background, job_id, file_path)

    return {
        "status": "accepted", 
        "message": "File is being processed in the background.", 
        "job_id": job_id
    }

@router.get("/result/{job_id}")
def get_analysis_result(job_id: str):
    """
    Endpoint to check the status of a specific background job
    and get the summarized results when finished.
    """
    job = feedback_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] == "processing":
        return {"status": "processing", "message": job.get("progress", "Initializing models... this will take a moment.")}
    
    if job["status"] == "failed":
        return {"status": "failed", "error": job["error"]}
        
    # Job completed
    return {"status": "completed", "data": job["result"]}


@router.get("/test")
def test():
    return {"message": "Feedback route working!"}
