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
from backend.database.models import User, Dataset, Notification
from backend.utils.sentiment import analyze_sentiment, extract_keywords_frequency, extract_keywords_tfidf
from backend.utils.churn_model import predict_churn

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

import time

def create_notification(db: Session, user_id: int, message: str):
    """
    Internal helper to create a system notification for a specific user.
    """
    notif = Notification(user_id=user_id, message=message, is_read=0)
    db.add(notif)
    db.commit()

def process_case_background(case_id: str, file_path: str, task_type: str):
    """
    Background worker with specialized status-notification synchronization.
    Lifecycle: pending -> processing -> completed.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            return
            
        # STEP 1: PROCESSING START
        dataset.review_status = "processing"
        db.commit()
        create_notification(db, dataset.user_id, f"Processing started for report: {dataset.filename}")
        
        # Artificial delay for guided workflow visibility
        time.sleep(3)
            
        out_results = {}
        if task_type == "Sentiment Analysis":
            CHUNK_SIZE, MAX_ROWS = 5000, 100_000 
            text_col = date_col = None
            total = positive = negative = neutral = 0
            results_preview, review_texts_full, enriched_chunks = [], [], []
            rows_processed = 0
            
            for chunk_df in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
                if rows_processed >= MAX_ROWS:
                    break
                if text_col is None:
                    possible_cols = ["review", "feedback", "comment", "text"]
                    text_col = next((c for c in chunk_df.columns if any(k in c.lower() for k in possible_cols)), None)
                    if not text_col: text_col = chunk_df.select_dtypes(include="object").columns[0]
                
                # Dynamic Date/Time column discovery for professional timeline charts
                if date_col is None:
                    date_col = next((c for c in chunk_df.columns if any(k in c.lower() for k in ["date", "timestamp", "created", "time"])), None)
                
                user_id_col = next((c for c in chunk_df.columns if any(k in c.lower() for k in ["userid", "user_id", "customerid", "customer_id", "id"])), None)
                chunk_reviews = chunk_df[text_col].fillna("").astype(str).tolist()
                chunk_results = [analyze_sentiment(r) for r in chunk_reviews]
                for res in chunk_results:
                    lbl = res["label"]
                    total += 1
                    if lbl == "POSITIVE": positive += 1
                    elif lbl == "NEGATIVE": negative += 1
                    else: neutral += 1
                review_texts_full.extend(chunk_reviews)
                if len(results_preview) < 1000:
                    for idx, (review, sentiment) in enumerate(zip(chunk_reviews, chunk_results)):
                        item = {"review": review, **sentiment}
                        if user_id_col: item[user_id_col] = str(chunk_df.iloc[idx][user_id_col])
                        # Preserve original timeline type (numeric or string) for visualization
                        if date_col: 
                            val = chunk_df.iloc[idx][date_col]
                            # Clean conversion for JSON serialization (handles int64/float64)
                            if pd.notnull(val):
                                item[date_col] = val.item() if hasattr(val, 'item') else val
                            else:
                                item[date_col] = None
                        results_preview.append(item)
                chunk_df["sentiment_label"] = [r["label"] for r in chunk_results]
                enriched_chunks.append(chunk_df)
                rows_processed += len(chunk_df)
            keywords_sample = review_texts_full[:5000]
            enriched_path = file_path.replace(case_id, f"enriched_{case_id}")
            pd.concat(enriched_chunks, ignore_index=True).to_csv(enriched_path, index=False)
            out_results = {
                "total": total, "positive": positive, "negative": negative, "neutral": neutral,
                "results": results_preview[:1000], 
                "freq_keywords": extract_keywords_frequency(keywords_sample, 15),
                "tfidf_keywords": extract_keywords_tfidf(keywords_sample, 15)
            }
        elif task_type == "Churn Prediction":
            total_customers = predicted_churn_total = 0
            all_predictions = []
            for chunk_idx, chunk in enumerate(pd.read_csv(file_path, chunksize=1000)):
                if chunk_idx >= 10: break
                results = predict_churn(chunk)
                if "error" in results:
                    if chunk_idx == 0: out_results = results
                    break
                total_customers += results.get("total_customers", 0)
                predicted_churn_total += results.get("predicted_churn", 0)
                all_predictions.extend(results.get("predictions", []))
            out_results = {
                "total_customers": total_customers, "predicted_churn": predicted_churn_total,
                "churn_rate": round(predicted_churn_total / total_customers * 100, 2) if total_customers > 0 else 0.0,
                "predictions": all_predictions[:1000]
            }
        
        # STEP 2: COMPLETE STATUS FIRST (Atomic Update)
        dataset.review_status = "completed"
        db.commit()
        db.refresh(dataset)
        
        # STEP 3: PERSIST RESULTS FILES
        results_path = f"{file_path}_results.json"
        with open(results_path, "w") as f:
            json.dump(out_results, f)
            
        # STEP 4: GENERATE NOTIFICATION SECOND (Zero-Race guaranteed)
        create_notification(db, dataset.user_id, f"Report generated successfully: {dataset.filename}")
        
    except Exception as e:
        db.rollback()
        if dataset:
            dataset.review_status = f"failed"
            db.commit()
            create_notification(db, dataset.user_id, f"Error processing report {dataset.filename}: {str(e)}")
    finally:
        db.close()

@router.get("/notifications/{username}")
def get_notifications(username: str):
    """
    Fetch all persistent notifications for a specific user ID.
    Sorted by latest first.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).all()
        return {
            "notifications": [
                {
                    "id": n.id, 
                    "message": n.message, 
                    "is_read": n.is_read, 
                    "created_at": n.created_at
                } 
                for n in notifs
            ]
        }
    finally:
        db.close()

@router.post("/notifications/read/{notif_id}")
def mark_notification_read(notif_id: int):
    """
    Mark a specific professional notification as 'Seen'.
    """
    db = SessionLocal()
    try:
        notif = db.query(Notification).filter(Notification.id == notif_id).first()
        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")
        notif.is_read = 1
        db.commit()
        return {"message": "Notification updated"}
    finally:
        db.close()

@router.post("/upload")
def upload_dataset(
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
        
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
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
                    "filename": ds.filename,
                    "notification_seen": ds.notification_seen
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
def retry_case(case_id: str, background_tasks: BackgroundTasks):
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

@router.post("/cases/{case_id}/acknowledge")
def acknowledge_case(case_id: str):
    """
    Mark a specific case as 'Notification Seen' by the user.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Case not found")
        dataset.notification_seen = 1
        db.commit()
        return {"message": "Acknowledged"}
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
