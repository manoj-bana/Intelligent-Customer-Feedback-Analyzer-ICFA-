from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel
import pandas as pd
import os
import io
import time
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
TEMP_DIR = os.path.join(UPLOAD_DIR, "temp")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def process_case_background(case_id: str, file_path: str, task_type: str):
    """
    Background worker for processing dataset analysis tasks.

    Args:
        case_id (str): Unique identifier for the analysis case.
        file_path (str): Local path to the uploaded CSV file.
        task_type (str): Type of analysis ('Sentiment Analysis' or 'Churn Prediction').
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            return

        if file_path.endswith((".xlsx", ".xls")):
            df_temp = pd.read_excel(file_path)
            new_file_path = file_path.rsplit('.', 1)[0] + '.csv'
            df_temp.to_csv(new_file_path, index=False)
            file_path = new_file_path

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
                
                chunk_reviews = chunk_df[text_col].fillna("").tolist()
                chunk_labels, chunk_scores = [], []
                for idx, review in enumerate(chunk_reviews):
                    sentiment = analyze_sentiment(str(review))
                    chunk_labels.append(sentiment["label"])
                    chunk_scores.append(sentiment["score"])
                    total += 1
                    if sentiment["label"] == "POSITIVE":
                        positive += 1
                    elif sentiment["label"] == "NEGATIVE":
                        negative += 1
                    else:
                        neutral += 1
                        
                    results_item = {"review": str(review), **sentiment}
                    if user_id_col:
                        results_item[user_id_col] = str(chunk_df.iloc[idx][user_id_col])
                    results_preview.append(results_item)
                    review_texts_preview.append(str(review))
                        
                chunk_df["SentimentLabel"], chunk_df["SentimentScore"] = chunk_labels, chunk_scores
                enriched_chunks.append(chunk_df)
                rows_processed += len(chunk_df)

            enriched_path = file_path.replace(case_id, f"enriched_{case_id}")
            full_df = pd.concat(enriched_chunks, ignore_index=True)
            full_df.to_csv(enriched_path, index=False)

            # --- Server-side User Aggregation ---
            user_engagement = []
            user_col = next(
                (col for col in ['user_id', 'userid', 'user']
                 if col.lower() in [c.lower() for c in full_df.columns]),
                None
            )
            if user_col:
                actual_user_col = next(
                    col for col in full_df.columns if col.lower() == user_col.lower()
                )

                def get_dom_sent(x):
                    mode = x.mode()
                    return mode[0] if not mode.empty else "UNKNOWN"

                def get_churn_score(x):
                    total = len(x)
                    if total == 0:
                        return 0.0
                    neg = (x.str.upper() == 'NEGATIVE').sum()
                    return round(neg / total, 2)

                agg_df = full_df.groupby(actual_user_col).agg(
                    Total_Comments=(text_col, 'count'),
                    Sentiment_Summary=('SentimentLabel', get_dom_sent),
                    Churn_Score=('SentimentLabel', get_churn_score)
                ).reset_index()

                agg_df.rename(columns={
                    actual_user_col: 'User ID',
                    'Total_Comments': 'Total Comments',
                    'Sentiment_Summary': 'Sentiment Summary',
                    'Churn_Score': 'Churn Score'
                }, inplace=True)
                user_engagement = agg_df.to_dict(orient='records')

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
                "user_engagement": user_engagement,
                "enriched_csv": csv_base64,
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
                "predictions": all_predictions[:1000]
            }
            
        results_path = f"{file_path}_results.json"
        with open(results_path, "w") as f:
            json.dump(out_results, f)

        dataset.review_status = "Completed"
        db.commit()

    except Exception as e:
        db.rollback()
        try:
            db.query(Dataset).filter(Dataset.case_id == case_id).update({"review_status": f"Error: {str(e)[:100]}"})
            db.commit()
        except:
            db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Existing Endpoints (CSV/XLSX direct upload — unchanged)
# ---------------------------------------------------------------------------

@router.post("/upload")
def upload_dataset(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    username: str = Form(...), 
    task_type: str = Form(...)
):
    """
    Handles multi-part file uploads and triggers background processing tasks.
    Supports CSV and XLSX files.
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
    Retrieves all processing cases associated with a specific user profile.
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

        try:
            if os.path.exists(dataset.file_path):
                os.remove(dataset.file_path)
        except OSError as e:
            print(f"Warning: Could not remove {dataset.file_path}: {e}")

        enriched_path = dataset.file_path.replace(case_id, f"enriched_{case_id}")
        try:
            if os.path.exists(enriched_path):
                os.remove(enriched_path)
        except OSError as e:
            print(f"Warning: Could not remove {enriched_path}: {e}")

        results_path = f"{dataset.file_path}_results.json"
        try:
            if os.path.exists(results_path):
                os.remove(results_path)
        except OSError as e:
            print(f"Warning: Could not remove {results_path}: {e}")

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
