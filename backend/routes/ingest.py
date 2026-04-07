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
import csv
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types
from sqlalchemy.orm import Session
from backend.database.db import SessionLocal
from backend.database.models import User, Dataset, Notification
from backend.utils.sentiment import analyze_sentiment, batch_analyze_sentiment, extract_keywords_frequency, extract_keywords_tfidf
from backend.utils.churn_model import predict_churn
load_dotenv()
gemini_client = genai.Client()

router = APIRouter()
UPLOAD_DIR = "uploads"
TEMP_DIR = os.path.join(UPLOAD_DIR, "temp")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    username: str = Form(...),
    task_type: str = Form(...)
):
    """
    Main ingestion endpoint. Handles file storage and spawns the background worker.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        case_id = str(uuid.uuid4())[:8]
        file_ext = file.filename.rsplit(".", 1)[-1].lower()
        file_name = f"{case_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        new_dataset = Dataset(
            case_id=case_id,
            user_id=user.id,
            filename=file.filename,
            file_path=file_path,
            task_type=task_type,
            review_status="pending"
        )
        db.add(new_dataset)
        db.commit()
        db.refresh(new_dataset)

        # Notify user instantly that processing has started
        create_notification(db, user.id, f"Processing started: {file.filename} is now being analyzed.")
        
        background_tasks.add_task(process_case_background, case_id, file_path, task_type)
        return {"message": "Upload successful", "case_id": case_id}
    finally:
        db.close()

@router.get("/cases/{username}")
def get_user_cases(username: str):
    """
    Fetch all analysis cases for a specific user.
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
                    "case_id": d.case_id,
                    "filename": d.filename,
                    "task_type": d.task_type,
                    "review_status": d.review_status,
                    "created_date": d.created_at
                }
                for d in datasets
            ]
        }
    finally:
        db.close()

@router.delete("/cases/{case_id}")
def delete_case(case_id: str):
    """
    Delete a specific analysis case and its associated files.
    """
    db = SessionLocal()
    try:
        ds = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not ds:
            raise HTTPException(status_code=404, detail="Case not found")
        
        # Cleanup files
        try:
            if os.path.exists(ds.file_path): os.remove(ds.file_path)
            res_p = f"{ds.file_path}_results.json"
            if os.path.exists(res_p): os.remove(res_p)
            enr_p = ds.file_path.replace(ds.case_id, f"enriched_{ds.case_id}")
            if os.path.exists(enr_p): os.remove(enr_p)
        except: pass
        
        db.delete(ds)
        db.commit()
        return {"message": "Deleted"}
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



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
    Background worker for processing dataset analysis tasks.
    Lifecycle: pending -> processing -> completed (synchronized for real-time notifications).
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset: return

        # Conversion logic for Excel datasets
        if file_path.lower().endswith((".xlsx", ".xls")):
            df_temp = pd.read_excel(file_path)
            new_file_path = file_path.rsplit('.', 1)[0] + '.csv'
            df_temp.to_csv(new_file_path, index=False)
            file_path = new_file_path
            
        # STEP 1: PROCESSING START
        dataset.review_status = "processing"
        db.commit()
        time.sleep(2) # Brief delay for guided UI visibility

        out_results = {}
        if task_type == "Sentiment Analysis":
            CHUNK_SIZE, MAX_ROWS = 5000, 100_000 
            text_col = date_col = None
            total = positive = negative = neutral = 0
            results_preview, review_texts_full, enriched_chunks = [], [], []
            rows_processed = 0
            
            for chunk_df in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
                if rows_processed >= MAX_ROWS: break
                
                # Progress update in DB
                try:
                    db.query(Dataset).filter(Dataset.case_id == case_id).update({
                        "extraction_status": f"Processing row {rows_processed}..."
                    })
                    db.commit()
                except:
                    db.rollback()

                if text_col is None:
                    possible_cols = ["review", "feedback", "comment", "text"]
                    text_col = next((c for c in chunk_df.columns if any(k in c.lower() for k in possible_cols)), None)
                    if not text_col: text_col = chunk_df.select_dtypes(include="object").columns[0]
                
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
                        if date_col: 
                            val = chunk_df.iloc[idx][date_col]
                            if pd.notnull(val): item[date_col] = val.item() if hasattr(val, 'item') else val
                            else: item[date_col] = None
                        results_preview.append(item)
                
                chunk_df["sentiment_label"] = [r["label"] for r in chunk_results]
                enriched_chunks.append(chunk_df)
                rows_processed += len(chunk_df)

            # --- Server-side User Engagement Insights ---
            full_df = pd.concat(enriched_chunks, ignore_index=True)
            
            # --- DEBUG LOGS (Requested) ---
            app_user = db.query(User).filter(User.id == dataset.user_id).first()
            user_name_raw = app_user.username if app_user else "UNKNOWN"
            unique_ids = []
            
            user_engagement = []
            user_col = next((col for col in ['user_id', 'userid', 'user', 'customer_id', 'customerid', 'id'] if col.lower() in [c.lower() for c in full_df.columns]), None)
            if not user_col:
                user_col = next((c for c in full_df.columns if 'id' in c.lower()), None)
                
            if user_col:
                actual_user_col = next(col for col in full_df.columns if col.lower() == user_col.lower())
                unique_ids = full_df[actual_user_col].astype(str).unique().tolist()
                
                # Filter logic: Standardize both to lowercase for matching
                # Requirement: "The user logs in, they should see their own feedback insights"
                filtered_df = full_df[full_df[actual_user_col].astype(str).str.lower() == user_name_raw.lower()]
                
                print(f"--- [ICFA DEBUG] Analysis ID: {case_id} ---")
                print(f"Current Dashboard User: {user_name_raw}")
                print(f"Dataset unique {actual_user_col} values: {unique_ids[:10]}...")
                print(f"Records matching dashboard user: {len(filtered_df)}")
                
                def get_dom_sent(x):
                    m = x.mode(); return m[0] if not m.empty else "UNKNOWN"
                def get_churn_score(x):
                    tot = len(x); return round((x.str.upper() == 'NEGATIVE').sum() / tot, 2) if tot > 0 else 0.0
                
                # Aggregate ALL for the overview, highlighted for specific user later
                agg_df = full_df.groupby(actual_user_col).agg(
                    Total_Comments=(text_col, 'count'),
                    Sentiment_Summary=('sentiment_label', get_dom_sent),
                    Churn_Score=('sentiment_label', get_churn_score)
                ).reset_index()
                agg_df.rename(columns={actual_user_col:'User ID', 'Total_Comments':'Total Comments', 'Sentiment_Summary':'Sentiment Summary', 'Churn_Score':'Churn Score'}, inplace=True)
                user_engagement = agg_df.to_dict(orient='records')
            else:
                print(f"--- [ICFA DEBUG] No ID column found in dataset. ---")

            enriched_path = file_path.replace(case_id, f"enriched_{case_id}")
            full_df.to_csv(enriched_path, index=False)
            
            csv_b64 = None
            if os.path.getsize(enriched_path) < (20 * 1024 * 1024):
                with open(enriched_path, "rb") as f: csv_b64 = base64.b64encode(f.read()).decode("utf-8")

            out_results = {
                "total": total, "positive": positive, "negative": negative, "neutral": neutral,
                "results": results_preview[:1000], "freq_keywords": extract_keywords_frequency(review_texts_full[:5000], 15),
                "tfidf_keywords": extract_keywords_tfidf(review_texts_full[:5000], 15),
                "user_engagement": user_engagement, "enriched_csv": csv_b64
            }

        elif task_type == "Churn Prediction":
            total_customers = predicted_churn_total = 0
            all_predictions = []
            for chunk_idx, chunk in enumerate(pd.read_csv(file_path, chunksize=1000)):
                # Progress update
                try:
                    db.query(Dataset).filter(Dataset.case_id == case_id).update({
                        "extraction_status": f"Churn Prediction: chunk {chunk_idx + 1}..."
                    }) 
                    db.commit()
                except: db.rollback()

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
        dataset.extraction_status = "Complete"
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


def process_image_extraction_background(case_id: str, image_path: str, content_type: str, task_type: str):
    """
    Background worker for OCR extraction and subsequent data analysis.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        prompt = "This image contains a data table. Extract ALL rows and columns exactly as shown without skipping or summarizing anything. Return only valid CSV text with headers in the first row. IMPORTANT: Any text field containing commas MUST be wrapped in double quotes. No explanation, no markdown, no code blocks — just raw CSV."
        
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash", # Corrected Model ID
            contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type=content_type)]
        )
        csv_text = response.text.strip()
        
        if csv_text.startswith("```"):
            lines = csv_text.splitlines()
            if lines[0].startswith("```"): lines = lines[1:]
            if lines and lines[-1].startswith("```"): lines = lines[:-1]
            csv_text = "\n".join(lines).strip()

        # Validate CSV briefly
        list(csv.reader(io.StringIO(csv_text)))
        
        # Save CSV and update dataset record
        csv_path = image_path.rsplit('.', 1)[0] + ".csv"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv_text)
            
        dataset.file_path = csv_path
        dataset.review_status = "Analyzing..."
        db.commit()

        # Now trigger the actual analysis
        process_case_background(case_id, csv_path, task_type)

    except Exception as e:
        db.rollback()
        db.query(Dataset).filter(Dataset.case_id == case_id).update({"review_status": f"Extraction Error: {str(e)[:100]}"})
        db.commit()
    finally:
        db.close()
        if os.path.exists(image_path):
            try: os.remove(image_path) # Cleanup raw image after extraction
            except: pass

@router.post("/upload-image")
def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    username: str = Form(...),
    task_type: str = Form(...)
):
    """
    Queues an image for OCR extraction and analysis. Returns 202 immediately.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        case_id = f"CA{uuid.uuid4().hex[:8].upper()}"
        temp_image_path = os.path.join(UPLOAD_DIR, f"{case_id}_{file.filename}")

        with open(temp_image_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        new_ds = Dataset(
            case_id=case_id,
            user_id=user.id,
            filename=f"{file.filename.rsplit('.', 1)[0]}.csv",
            file_path=temp_image_path,
            source="image",
            review_status="Extracting Table...",
            extraction_status="OCR in progress",
            task_type=task_type
        )
        db.add(new_ds)
        db.commit()

        background_tasks.add_task(
            process_image_extraction_background,
            case_id=case_id,
            image_path=temp_image_path,
            content_type=file.content_type or 'image/png',
            task_type=task_type
        )
        return {"message": "Image queued for extraction", "case_id": case_id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.delete("/cases/all/{username}")
def delete_all_cases(username: str):
    """
    Delete all cases and associated files for a user.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        datasets = db.query(Dataset).filter(Dataset.user_id == user.id).all()
        for ds in datasets:
            try:
                if os.path.exists(ds.file_path): os.remove(ds.file_path)
                res_p = f"{ds.file_path}_results.json"
                if os.path.exists(res_p): os.remove(res_p)
                enr_p = ds.file_path.replace(ds.case_id, f"enriched_{ds.case_id}")
                if os.path.exists(enr_p): os.remove(enr_p)
            except: pass
            db.delete(ds)
        db.commit()
        return {"message": "All cases deleted"}
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
def get_case_results(case_id: str, page: int = 1, limit: int = 10, search: str = ""):
    """
    Retrieve analysis results with server-side pagination and search.
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
            data = json.load(f)

        # Handle Pagination/Search for 'results' or 'predictions' lists
        list_key = "results" if "results" in data else "predictions"
        if list_key in data:
            full_list = data[list_key]
            
            # Apply Search
            if search:
                query = search.lower()
                full_list = [
                    item for item in full_list 
                    if any(query in str(v).lower() for v in item.values())
                ]
            
            total_count = len(full_list)
            start = (page - 1) * limit
            end = start + limit
            
            data[list_key] = full_list[start:end]
            data["pagination"] = {
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": (total_count - 1) // limit + 1
            }
            
            # Remove giant CSV if it's not the download request (optional optimization)
            # if limit < 100: data.pop("enriched_csv", None)
            
        return data
    finally:
        db.close()
