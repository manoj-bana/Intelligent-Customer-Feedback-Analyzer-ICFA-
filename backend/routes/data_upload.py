from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Query, Depends
from pydantic import BaseModel
import pandas as pd
import os
import io
import uuid
import shutil
import json
import base64
import csv
import traceback
import datetime
from sqlalchemy.orm import Session
from backend.database.db import SessionLocal, get_db
from backend.database.models import User, Dataset, Notification, Organization
from backend.models.config import CompanyConfig
from backend.services.feedback_classifier import batch_analyze_sentiment, extract_keywords_frequency, extract_keywords_tfidf
from backend.services.churn_predictor import predict_churn
from backend.auth import get_current_user
from backend.utils.column_mapper import map_schema
from analytics_dashboard.data_loader import aggregate_user_data

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    username: str = Form(...),
    task_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    MAX_FILE_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 50MB.")
    await file.seek(0)

    file_ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    if file_ext not in ["csv", "xlsx", "xls"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only CSV/Excel allowed.")
    
    try:
        case_id = str(uuid.uuid4())[:8]
        file_name = f"{case_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        new_dataset = Dataset(
            case_id=case_id,
            user_id=current_user.id,
            org_id=current_user.org_id,
            filename=file.filename,
            file_path=file_path,
            task_type=task_type,
            review_status="pending",
            notification_seen=0
        )
        db.add(new_dataset)
        db.commit()
        
        background_tasks.add_task(process_data_pipeline, case_id, file_path, task_type)
        return {"message": "Upload successful", "case_id": case_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

def process_data_pipeline(case_id: str, file_path: str, task_type: str):
    db = SessionLocal()
    dataset = None
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset: return

        # 1. Load Data
        if file_path.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
            
        # 2. Schema Mapping
        config = db.query(CompanyConfig).filter(CompanyConfig.org_id == dataset.org_id).first()
        df_mapped, mapping_info = map_schema(df, config.column_mapper if config else None)
        
        print(f"[PIPELINE] Task: {task_type} | Case: {case_id}")
        print(f"[PIPELINE] Mapping Info: {mapping_info['mapped_columns']}")
        
        # 3. Processing
        dataset.review_status = "processing"
        db.commit()

        results = {}
        if task_type == "Sentiment Analysis":
            texts = df_mapped["feedback_text"].fillna("").astype(str).tolist()
            sentiment_results = batch_analyze_sentiment(texts, config=config)
            
            # Enrich DataFrame
            df_mapped["sentiment_label"] = [r["label"] for r in sentiment_results]
            df_mapped["sentiment_score"] = [r["score"] for r in sentiment_results]
            
            # Aggregate User Engagement
            agg_df = aggregate_user_data(df_mapped)
            user_engagement = agg_df.to_dict(orient="records") if agg_df is not None else []
            
            # Keywords
            freq_kw = extract_keywords_frequency(texts)
            tfidf_kw = extract_keywords_tfidf(texts)
            
            # Sentiment Counts (Using config labels if available)
            pos_label = getattr(config, "pos_label", "Positive")
            neg_label = getattr(config, "neg_label", "Negative")
            neu_label = getattr(config, "neu_label", "Neutral")

            results = {
                "total": len(df_mapped),
                "positive": len(df_mapped[df_mapped["sentiment_label"] == pos_label]),
                "negative": len(df_mapped[df_mapped["sentiment_label"] == neg_label]),
                "neutral": len(df_mapped[df_mapped["sentiment_label"] == neu_label]),
                "results": df_mapped.to_dict(orient="records")[:1000], 
                "freq_keywords": freq_kw,
                "tfidf_keywords": tfidf_kw,
                "user_engagement": user_engagement,
                "enriched_csv": base64.b64encode(df_mapped.to_csv(index=False).encode()).decode()
            }
        
        elif task_type == "Churn Prediction":
            churn_res = predict_churn(df_mapped, config=config)
            
            # If churn service returned an error (model missing, schema issues),
            # mark the dataset as failed and record the error so the frontend
            # shows a useful message instead of misleading zeros.
            if isinstance(churn_res, dict) and churn_res.get("error"):
                err_msg = churn_res.get("error")
                # Persist failure state and message
                dataset.review_status = "failed"
                dataset.error_message = err_msg if isinstance(err_msg, str) else str(err_msg)
                db.commit()
                print(f"[CHURN PIPELINE] Failed: {err_msg}")
                return

            # predictions come from service
            predictions = churn_res.get("predictions", [])
            
            results = {
                "total_customers": churn_res.get("total_customers", len(df_mapped)),
                "predicted_churn": churn_res.get("predicted_churn", 0),
                "churn_rate": churn_res.get("churn_rate", 0),
                "predictions": predictions,
                "enriched_csv": base64.b64encode(df_mapped.to_csv(index=False).encode()).decode()
            }

        # 4. Finalize
        dataset.review_status = "completed"
        dataset.result_data = json.dumps(results)
        dataset.last_analyzed = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        db.commit()
        
    except Exception as e:
        print(f"[PIPELINE ERROR] {traceback.format_exc()}")
        db.rollback()
        if dataset:
            dataset.review_status = "failed"
            dataset.error_message = str(e)
            db.commit()
    finally:
        db.close()

@router.post("/cases/{case_id}/retry")
async def retry_case(case_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Reprocess a case that might have failed or needs updating.
    """
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Case not found")

        dataset.review_status = "pending"
        db.commit()

        background_tasks.add_task(
            process_data_pipeline,
            case_id=dataset.case_id,
            file_path=dataset.file_path,
            task_type=dataset.task_type
        )
        return {"message": "Case queued"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- Image Extraction ---

# google.genai is an optional dependency (used for Gemini image extraction).
# Import lazily and tolerate ImportError so the whole app can run without it.
try:
    import google.genai as genai
    from google.genai import types
    gemini_client = genai.Client()
    GEMINI_AVAILABLE = True
except Exception:
    genai = None
    types = None
    gemini_client = None
    GEMINI_AVAILABLE = False

def process_image_extraction_background(case_id: str, image_path: str, content_type: str, task_type: str):
    """
    Background worker for OCR extraction and subsequent data analysis.
    """
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset: return

        if not GEMINI_AVAILABLE:
            # Mark dataset as failed due to missing optional dependency
            db.query(Dataset).filter(Dataset.case_id == case_id).update({
                "review_status": "Extraction Error: Gemini client not available"
            })
            db.commit()
            return

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        prompt = "This image contains a data table. Extract ALL rows and columns exactly as shown without skipping or summarizing anything. Return only valid CSV text with headers in the first row. IMPORTANT: Any text field containing commas MUST be wrapped in double quotes. No explanation, no markdown, no code blocks — just raw CSV."
        
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type=content_type)]
        )
        csv_text = response.text.strip()
        
        # Cleanup markdown formatting if Gemini adds it
        if csv_text.startswith("```"):
            lines = csv_text.splitlines()
            if lines[0].startswith("```"): lines = lines[1:]
            if lines and lines[-1].startswith("```"): lines = lines[:-1]
            csv_text = "\n".join(lines).strip()

        # Save CSV and update dataset record
        csv_path = image_path.rsplit('.', 1)[0] + ".csv"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv_text)
            
        dataset.file_path = csv_path
        dataset.review_status = "Analyzing..."
        db.commit()

        # Trigger actual analysis pipeline
        process_data_pipeline(case_id, csv_path, task_type)

    except Exception as e:
        db.rollback()
        db.query(Dataset).filter(Dataset.case_id == case_id).update({"review_status": f"Extraction Error: {str(e)[:100]}"})
        db.commit()
    finally:
        db.close()
        if os.path.exists(image_path):
            try: os.remove(image_path)
            except: pass

@router.post("/upload-image")
def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    username: str = Form(...),
    task_type: str = Form(...)
):
    """
    Queues an image for OCR extraction and analysis.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not GEMINI_AVAILABLE:
            raise HTTPException(status_code=503, detail="Image extraction is unavailable: optional google.genai package is not installed.")

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
    finally:
        db.close()


@router.delete("/cases/all/{username}")
def delete_all_cases(username: str, db: Session = Depends(get_db)):
    """
    Delete all cases and associated files for a user.
    """
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
             user = db.query(User).filter(User.username.ilike(username)).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        
        datasets = db.query(Dataset).filter(Dataset.user_id == user.id).all()
        for ds in datasets:
            try:
                if os.path.exists(ds.file_path): 
                    os.remove(ds.file_path)
            except: 
                pass
            db.delete(ds)
        db.commit()
        return {"message": "All cases deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cases/{username}")
def get_user_cases(username: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        
        query = db.query(Dataset)
        if current_user.role != "admin" and current_user.username != "admin":
             query = query.filter(Dataset.org_id == current_user.org_id)
             query = query.filter(Dataset.user_id == current_user.id)
            
        datasets = query.order_by(Dataset.id.desc()).all()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications/{username}")
def get_notifications(username: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).all()
        return {
            "notifications": [
                {"id": n.id, "message": n.message, "is_read": n.is_read, "created_at": n.created_at} 
                for n in notifs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notifications/read/{notif_id}")
def mark_notification_read(notif_id: int, db: Session = Depends(get_db)):
    try:
        notif = db.query(Notification).filter(Notification.id == notif_id).first()
        if notif:
            notif.is_read = 1
            db.commit()
        return {"message": "Updated"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cases/{case_id}")
def delete_case(case_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        ds = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not ds: raise HTTPException(status_code=404, detail="Case not found")
        if os.path.exists(ds.file_path): 
            try: os.remove(ds.file_path)
            except: pass
        db.delete(ds)
        db.commit()
        return {"message": "Deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{case_id}")
def get_case_results(
    case_id: str, 
    page: int = 1, 
    limit: int = 10, 
    search: str = "",
    sentiment: str = None,
    sort_by: str = None,
    sort_order: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        dataset = db.query(Dataset).filter(Dataset.case_id == case_id).first()
        if not dataset: raise HTTPException(status_code=404, detail="Case not found")
        
        if not dataset.result_data:
            return {"status": dataset.review_status, "error": dataset.error_message}
            
        data = json.loads(dataset.result_data)
        
        # Pagination, Search, Filter Logic
        list_key = "results" if "results" in data else "predictions"
        if list_key in data:
            full_list = data[list_key]
            
            # 1. Apply Search
            if search:
                q = search.lower()
                full_list = [i for i in full_list if any(q in str(v).lower() for v in i.values())]
            
            # 2. Apply Sentiment Filter
            if sentiment and sentiment.lower() != "all":
                sent_lower = sentiment.lower()
                full_list = [
                    item for item in full_list
                    if str(item.get("sentiment_label", item.get("label", ""))).lower() == sent_lower
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
                    pass
            
            total = len(full_list)
            start = (page - 1) * limit
            end = start + limit
            data[list_key] = full_list[start:end]
            data["pagination"] = {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total - 1) // limit + 1 if total > 0 else 1
            }
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
   