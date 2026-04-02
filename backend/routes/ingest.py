from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
import pandas as pd
import os
import io
import uuid
import shutil
import json
import base64
from sqlalchemy.orm import Session
from backend.database.db import SessionLocal
from backend.database.models import User, Dataset
from backend.utils.sentiment import analyze_sentiment, extract_keywords_frequency, extract_keywords_tfidf
from backend.utils.churn_model import predict_churn

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def process_case_background(case_id: str, file_path: str, task_type: str):
    """
    Background worker to process uploaded data for Sentiment Analysis or Churn Prediction.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            return
            
        out_results = {}
        if task_type == "Sentiment Analysis":
            CHUNK_SIZE, MAX_ROWS = 5000, 500_000
            text_col = None
            total = positive = negative = neutral = 0
            results_preview, review_texts_preview, enriched_chunks = [], [], []
            rows_processed = 0
            
            for chunk_df in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
                if rows_processed >= MAX_ROWS:
                    break
                    
                if text_col is None:
                    for col in chunk_df.columns:
                        if any(k in col.lower() for k in ["review", "feedback", "comment", "text"]):
                            text_col = col
                            break
                    if not text_col:
                        text_col = chunk_df.select_dtypes(include="object").columns[0]
                
                # Identify user ID column to preserve
                user_id_col = next((c for c in chunk_df.columns if any(k in c.lower() for k in ["userid", "user_id", "customerid", "customer_id", "id"])), None)
                
                # Batch analyze sentiment for much higher throughput
                chunk_reviews = chunk_df[text_col].fillna("").astype(str).tolist()
                
                chunk_labels = []
                chunk_scores = []
                
                # Using a local reference for speed in the loop
                local_analyze = analyze_sentiment
                
                for review in chunk_reviews:
                    res = local_analyze(review)
                    label = res["label"]
                    score = res["score"]
                    
                    chunk_labels.append(label)
                    chunk_scores.append(score)
                    
                    total += 1
                    if label == "POSITIVE": positive += 1
                    elif label == "NEGATIVE": negative += 1
                    else: neutral += 1
                
                if len(results_preview) < 1000:
                    for i, (rev, lbl, scr) in enumerate(zip(chunk_reviews, chunk_labels, chunk_scores)):
                        if len(results_preview) >= 1000: break
                        item = {"review": rev, "label": lbl, "score": scr}
                        if user_id_col: item[user_id_col] = str(chunk_df.iloc[i][user_id_col])
                        results_preview.append(item)
                        review_texts_preview.append(rev)

                chunk_df["SentimentLabel"], chunk_df["SentimentScore"] = chunk_labels, chunk_scores
                enriched_chunks.append(chunk_df)
                rows_processed += len(chunk_df)
                
            enriched_path = file_path.replace(case_id, f"enriched_{case_id}")
            full_df = pd.concat(enriched_chunks, ignore_index=True)
            full_df.to_csv(enriched_path, index=False)
            
            csv_base64 = None
            if os.path.exists(enriched_path) and os.path.getsize(enriched_path) < (25 * 1024 * 1024):
                with open(enriched_path, "rb") as f:
                    csv_base64 = base64.b64encode(f.read()).decode("utf-8")
                    
            out_results = {
                "total": total, 
                "positive": positive, 
                "negative": negative, 
                "neutral": neutral,
                "results": results_preview, 
                "freq_keywords": extract_keywords_frequency(review_texts_preview, 15),
                "tfidf_keywords": extract_keywords_tfidf(review_texts_preview, 15), 
                "enriched_csv": csv_base64
            }
        elif task_type == "Churn Prediction":
            total_customers = predicted_churn_total = 0
            all_predictions = []
            for chunk_idx, chunk in enumerate(pd.read_csv(file_path, chunksize=1000)):
                if chunk_idx >= 10:
                    break
                results = predict_churn(chunk)
                if "error" in results:
                    if chunk_idx == 0:
                        out_results = results
                    break
                total_customers += results.get("total_customers", 0)
                predicted_churn_total += results.get("predicted_churn", 0)
                if len(all_predictions) < 1000:
                    all_predictions.extend(results.get("predictions", []))
            
            out_results = {
                "total_customers": total_customers, 
                "predicted_churn": predicted_churn_total,
                "churn_rate": round(predicted_churn_total / total_customers * 100, 2) if total_customers > 0 else 0.0,
                "predictions": all_predictions
            }

            
        results_path = f"{file_path}_results.json"
        with open(results_path, "w") as f:
            json.dump(out_results, f)
            
        dataset.review_status = "Completed"
        db.commit()
    except Exception as e:
        db.rollback()
        if dataset:
            dataset.review_status = f"Error: {e}"
            db.commit()
    finally:
        db.close()

@router.post("/upload")
async def upload_dataset(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    username: str = Form(...), 
    task_type: str = Form(...)
):
    """
    Endpoint to upload a dataset and trigger background processing.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        case_id = f"CA{uuid.uuid4().hex[:8].upper()}"
        temp_file_path = os.path.join(UPLOAD_DIR, f"{case_id}_{file.filename}")
        
        # Async write for faster response
        content = await file.read()
        with open(temp_file_path, "wb") as buffer:
            buffer.write(content)
            
        new_ds = Dataset(
            case_id=case_id, 
            user_id=user.id, 
            filename=file.filename, 
            file_path=temp_file_path, 
            source="web", 
            review_status="Pending Review", 
            extraction_status="1 of 1", 
            task_type=task_type
        )
        db.add(new_ds)
        db.commit()
        db.refresh(new_ds)
        
        background_tasks.add_task(
            process_case_background, 
            case_id=new_ds.case_id, 
            file_path=temp_file_path, 
            task_type=task_type
        )
        return {"message": "File uploaded", "case_id": new_ds.case_id, "filename": new_ds.filename}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/cases/{username}")
def get_user_cases(username: str):
    """
    Fetch all analysis cases associated with a specific user.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        datasets = db.query(Dataset).filter(Dataset.user_id == user.id).order_by(Dataset.id.desc()).all()
        return {
            "cases": [
                {
                    "case_id": ds.case_id, 
                    "created_date": ds.created_at, 
                    "source": ds.source, 
                    "review_status": ds.review_status, 
                    "extraction_status": ds.extraction_status, 
                    "task_type": ds.task_type, 
                    "filename": ds.filename
                } 
                for ds in datasets
            ]
        }
    finally:
        db.close()

@router.delete("/cases/{case_id}")
def delete_case(case_id: str):
    """
    Delete a specific case and its associated files.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Case not found")
            
        if os.path.exists(dataset.file_path):
            os.remove(dataset.file_path)
            
        enriched_path = dataset.file_path.replace(case_id, f"enriched_{case_id}")
        if os.path.exists(enriched_path):
            os.remove(enriched_path)
            
        results_path = f"{dataset.file_path}_results.json"
        if os.path.exists(results_path):
            os.remove(results_path)
            
        db.delete(dataset)
        db.commit()
        return {"message": "Case deleted"}
    finally:
        db.close()

@router.post("/cases/{case_id}/retry")
async def retry_case(case_id: str, background_tasks: BackgroundTasks):
    """
    Reprocess a case that might have failed or needs updating.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Case not found")
            
        dataset.review_status = "Pending Review"
        db.commit()
        
        background_tasks.add_task(
            process_case_background, 
            case_id=dataset.case_id, 
            file_path=dataset.file_path, 
            task_type=dataset.task_type
        )
        return {"message": "Case queued"}
    finally:
        db.close()

@router.get("/results/{case_id}")
def get_case_results(case_id: str):
    """
    Retrieve analysis results for a completed case.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Case not found")
            
        results_path = f"{dataset.file_path}_results.json"
        if not os.path.exists(results_path):
            raise HTTPException(status_code=404, detail="Results not ready")
            
        with open(results_path, "r") as f:
            return json.load(f)
    finally:
        db.close()
@router.delete("/cases/all/{username}")
def delete_all_cases(username: str):
    """
    Delete all cases associated with a specific user.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        datasets = db.query(Dataset).filter(Dataset.user_id == user.id).all()
        for dataset in datasets:
            # Delete physical files
            if os.path.exists(dataset.file_path):
                os.remove(dataset.file_path)
            
            enriched_path = dataset.file_path.replace(dataset.case_id, f"enriched_{dataset.case_id}")
            if os.path.exists(enriched_path):
                os.remove(enriched_path)
            
            results_path = f"{dataset.file_path}_results.json"
            if os.path.exists(results_path):
                os.remove(results_path)
                
            db.delete(dataset)
            
        db.commit()
        return {"message": f"Successfully deleted all {len(datasets)} cases"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
