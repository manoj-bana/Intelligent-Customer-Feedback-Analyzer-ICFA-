from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Query, Depends
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
import traceback
import datetime
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types
from sqlalchemy.orm import Session
from backend.database.db import SessionLocal
from backend.database.models import User, Dataset, Notification, Organization, SentimentConfig, ChurnConfig
from backend.utils.sentiment import analyze_sentiment, batch_analyze_sentiment, extract_keywords_frequency, extract_keywords_tfidf
from backend.utils.churn_model import predict_churn
from backend.auth import get_current_user, get_current_org
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
    task_type: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """
    Main ingestion endpoint. Handles file storage and spawns the background worker.
    """
    # 1. Validation: File Size (max 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 50MB.")

    # 2. Validation: MIME Type / Extension
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in ["csv", "xlsx", "xls"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only CSV/Excel allowed.")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # --- Upsert logic: Update existing record if found, else create new ---
        existing = db.query(Dataset).filter(
            Dataset.user_id == user.id,
            Dataset.filename == file.filename,
            Dataset.task_type == task_type
        ).first()

        if existing:
            if existing.review_status in ["pending", "processing"]:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"'{file.filename}' is already queued or being processed for "
                        f"{task_type} (Case ID: {existing.case_id}). "
                        "Wait for it to complete before re-uploading."
                    )
                )
            
            # If completed/failed, we RE-USE the existing record (Upsert)
            case_id = existing.case_id
            dataset = existing
            dataset.review_status = "pending"
            dataset.extraction_status = "1 of 1"
            dataset.result_data = None
            dataset.error_message = None
            dataset.created_at = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
            # Use existing file path but we will overwrite the file
            file_path = dataset.file_path
        else:
            # Create a brand new record
            case_id = str(uuid.uuid4())[:8]
            file_name = f"{case_id}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, file_name)
            
            dataset = Dataset(
                case_id=case_id,
                user_id=user.id,
                org_id=user.org_id,
                filename=file.filename,
                file_path=file_path,
                task_type=task_type,
                review_status="pending"
            )
            db.add(dataset)

        # Overwrite/Save file content
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db.commit()
        db.refresh(dataset)

        # Notify user instantly
        create_notification(db, user.id, f"Processing started: {file.filename} is now being analyzed.")
        
        background_tasks.add_task(process_case_background, case_id, file_path, task_type)
        return {"message": "Upload successful", "case_id": case_id}
    finally:
        db.close()

@router.get("/cases/{username}")
def get_user_cases(username: str, current_user: User = Depends(get_current_user)):
    """
    Fetch all analysis cases for a specific user.
    """
    if current_user.username != username and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view these cases")
    db = SessionLocal()
    try:
        user = current_user
        
        # Isolation: Filter by user.id AND org_id (though org_id is stronger)
        datasets = db.query(Dataset).filter(
            Dataset.user_id == user.id,
            Dataset.org_id == current_user.org_id
        ).order_by(Dataset.id.desc()).all()
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
            
        # STEP 1: LOAD TENANT CONFIG
        sent_cfg = None
        churn_cfg = None
        if dataset.org_id:
            org = db.query(Organization).filter(Organization.id == dataset.org_id).first()
            if org:
                sent_cfg = org.sentiment_config
                churn_cfg = org.churn_config
        
        # STEP 2: PROCESSING START
        dataset.review_status = "processing"
        db.commit()

        out_results = {}
        if task_type == "Sentiment Analysis":
            CHUNK_SIZE, MAX_ROWS = 5000, 100_000 
            text_col = date_col = user_id_col = None
            total = positive = negative = neutral = 0
            results_preview, review_texts_full, enriched_chunks = [], [], []
            rows_processed = 0
            chunk_index = 0
            
            for chunk_df in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
                if rows_processed >= MAX_ROWS: break
                chunk_index += 1
                
                # Progress update in DB (every 3rd chunk to reduce write overhead)
                if chunk_index % 3 == 1:
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
                
                if user_id_col is None:
                    user_id_col = next((c for c in chunk_df.columns if any(k in c.lower() for k in ["userid", "user_id", "customerid", "customer_id", "id"])), None)

                chunk_reviews = chunk_df[text_col].fillna("").astype(str).tolist()
                
                # PERF: Use batch analysis (single model load, tight loop)
                chunk_results = batch_analyze_sentiment(chunk_reviews, config=sent_cfg)
                
                # Get labels for counting
                p_lbl = getattr(sent_cfg, "pos_label", "Positive")
                n_lbl = getattr(sent_cfg, "neg_label", "Negative")
                
                for res in chunk_results:
                    lbl = res["label"]
                    total += 1
                    if lbl == p_lbl: positive += 1
                    elif lbl == n_lbl: negative += 1
                    else: neutral += 1
                
                review_texts_full.extend(chunk_reviews)
                if len(results_preview) < 1000:
                    # PERF: Use vectorized access via .values instead of .iloc per row
                    uid_vals = chunk_df[user_id_col].values if user_id_col else None
                    date_vals = chunk_df[date_col].values if date_col else None
                    for idx, (review, sentiment) in enumerate(zip(chunk_reviews, chunk_results)):
                        if len(results_preview) >= 1000: break
                        item = {"review": review, **sentiment}
                        if uid_vals is not None: item[user_id_col] = str(uid_vals[idx])
                        if date_vals is not None:
                            val = date_vals[idx]
                            item[date_col] = val.item() if hasattr(val, 'item') else (val if pd.notnull(val) else None)
                        results_preview.append(item)
                
                chunk_df["sentiment_label"] = [r["label"] for r in chunk_results]
                chunk_df["sentiment_score"] = [r["score"] for r in chunk_results]
                enriched_chunks.append(chunk_df)
                rows_processed += len(chunk_df)

            # --- Server-side User Engagement Insights ---
            full_df = pd.concat(enriched_chunks, ignore_index=True)
            
            app_user = db.query(User).filter(User.id == dataset.user_id).first()
            user_name_raw = app_user.username if app_user else "UNKNOWN"
            
            user_engagement = []
            user_col = next((col for col in ['user_id', 'userid', 'user', 'customer_id', 'customerid', 'id'] if col.lower() in [c.lower() for c in full_df.columns]), None)
            if not user_col:
                user_col = next((c for c in full_df.columns if 'id' in c.lower()), None)
                
            if user_col:
                actual_user_col = next(col for col in full_df.columns if col.lower() == user_col.lower())
                
                def get_dom_sent(x):
                    m = x.mode(); return m[0] if not m.empty else "UNKNOWN"
                def count_pos(x):
                    return int((x.str.upper() == 'POSITIVE').sum())
                def count_neg(x):
                    return int((x.str.upper() == 'NEGATIVE').sum())
                def count_neu(x):
                    return int((x.str.upper() == 'NEUTRAL').sum())
                def get_churn_score(x):
                    tot = len(x); return round((x == n_lbl).sum() / tot, 2) if tot > 0 else 0.0
                
                # Check if score column exists in full_df
                score_col_name = next((c for c in full_df.columns if c.lower() in ['score', 'sentiment_score']), None)
                
                agg_spec = {
                    'Positive': ('sentiment_label', count_pos),
                    'Negative': ('sentiment_label', count_neg),
                    'Neutral': ('sentiment_label', count_neu),
                    'Dominant_Sentiment': ('sentiment_label', get_dom_sent),
                    'Churn_Risk': ('sentiment_label', get_churn_score),
                }
                if score_col_name:
                    agg_spec['Avg_Score'] = (score_col_name, lambda x: round(x.mean(), 3))
                
                agg_df = full_df.groupby(actual_user_col).agg(**agg_spec).reset_index()
                
                rename_map = {
                    actual_user_col: 'User ID',
                    'Positive': '👍 Positive',
                    'Negative': '👎 Negative',
                    'Neutral': '😐 Neutral',
                    'Dominant_Sentiment': 'Dominant Sentiment',
                    'Churn_Risk': 'Churn Risk',
                }
                if score_col_name:
                    rename_map['Avg_Score'] = 'Sentiment Score'
                
                agg_df.rename(columns=rename_map, inplace=True)
                user_engagement = agg_df.to_dict(orient='records')

            enriched_path = file_path.replace(case_id, f"enriched_{case_id}")
            full_df.to_csv(enriched_path, index=False)
            
            csv_b64 = None
            if os.path.getsize(enriched_path) < (20 * 1024 * 1024):
                with open(enriched_path, "rb") as f: csv_b64 = base64.b64encode(f.read()).decode("utf-8")

            # PERF: Cap keyword input at 3000 texts (still statistically sound, much faster TF-IDF)
            kw_sample = review_texts_full[:3000]
            out_results = {
                "total": total, "positive": positive, "negative": negative, "neutral": neutral,
                "results": results_preview[:1000], "freq_keywords": extract_keywords_frequency(kw_sample, 15),
                "tfidf_keywords": extract_keywords_tfidf(kw_sample, 15),
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

                results = predict_churn(chunk, config=churn_cfg)
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
        dataset.result_data = json.dumps(out_results)
        dataset.last_analyzed = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        dataset.extraction_status = "Complete"
        db.commit()
        
        # STEP 3: GENERATE NOTIFICATION
        create_notification(db, dataset.user_id, f"Report generated successfully: {dataset.filename}")
        
    except Exception as e:
        print(f"[BACKGROUND] Error processing {case_id}: {traceback.format_exc()}")
        db.rollback()
        if dataset:
            dataset.review_status = "failed"
            dataset.error_message = str(e)
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
            org_id=user.org_id,
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
        if not user:
            user = db.query(User).filter(User.username.ilike(username)).first()
            
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
def get_case_results(
    case_id: str, 
    page: int = 1, 
    limit: int = 10, 
    search: str = "", 
    sentiment: str = None,
    sort_by: str = None,
    sort_order: str = "desc",
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve analysis results with server-side pagination and search.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Case not found")

        if dataset.org_id != current_user.org_id and current_user.role != "super_admin":
            raise HTTPException(status_code=403, detail="Silo violation: Access denied to this organization's data")

        if not dataset.result_data:
            if dataset.review_status == "failed":
                raise HTTPException(status_code=500, detail=f"Job failed: {dataset.error_message}")
            raise HTTPException(status_code=404, detail="Results not ready or not found")

        data = json.loads(dataset.result_data)

        # Handle Pagination/Search for 'results' or 'predictions' lists
        list_key = "results" if "results" in data else "predictions"
        if list_key in data:
            full_list = data[list_key]
            
            # 1. Apply Search
            if search:
                query = search.lower()
                full_list = [
                    item for item in full_list 
                    if any(query in str(v).lower() for v in item.values())
                ]
            
            # 2. Apply Sentiment Filter
            if sentiment and sentiment.lower() != "all":
                # Matches either 'sentiment_label' or 'label'
                full_list = [
                    item for item in full_list 
                    if str(item.get("sentiment_label", item.get("label", ""))).lower() == sentiment.lower()
                ]

            # 3. Apply Sorting
            if sort_by:
                reverse = (sort_order.lower() == "desc")
                try:
                    full_list = sorted(
                        full_list, 
                        key=lambda x: (x.get(sort_by) is None, x.get(sort_by)), 
                        reverse=reverse
                    )
                except Exception:
                    pass # Ignore if sorting fails due to type mismatch
            
            total_count = len(full_list)
            start = (page - 1) * limit
            end = start + limit
            
            data[list_key] = full_list[start:end]
            data["pagination"] = {
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": (total_count - 1) // limit + 1 if total_count > 0 else 1
            }
            
            # Remove giant CSV if it's not the download request (optional optimization)
            # if limit < 100: data.pop("enriched_csv", None)
            
        return data
    finally:
        db.close()

# --- Admin Dataset Management ---
# Admin endpoints removed (now in admin.py)
