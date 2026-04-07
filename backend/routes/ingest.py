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
from backend.database.models import User, Dataset
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

                # Progress update in DB
                try:
                    db.query(Dataset).filter(Dataset.case_id == case_id).update({
                        "extraction_status": f"Processing row {rows_processed}..."
                    })
                    db.commit()
                except:
                    db.rollback()

                if text_col is None:
                    for col in chunk_df.columns:
                        if any(k in col.lower() for k in ["review", "feedback", "comment", "text"]):
                            text_col = col
                            break
                    if not text_col:
                        text_col = chunk_df.select_dtypes(include="object").columns[0]
                
                chunk_results = batch_analyze_sentiment(chunk_reviews)
                
                # Convert chunk to list of dicts for easier preview management
                chunk_dicts = chunk_df.to_dict(orient="records")
                
                for idx, res in enumerate(chunk_results):
                    total += 1
                    if res["label"] == "POSITIVE": positive += 1
                    elif res["label"] == "NEGATIVE": negative += 1
                    else: neutral += 1
                    
                    if len(results_preview) < 10000:
                        # Include BOTH original columns and sentiment results
                        full_record = chunk_dicts[idx].copy()
                        full_record.update(res)
                        results_preview.append(full_record)
                        review_texts_preview.append(str(full_record.get(text_col, "")))
                        
                chunk_df["SentimentLabel"] = [r["label"] for r in chunk_results]
                chunk_df["SentimentScore"] = [r["score"] for r in chunk_results]
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
                "total_customers": total_customers,
                "predicted_churn": predicted_churn_total,
                "churn_rate": round(predicted_churn_total / total_customers * 100, 2) if total_customers > 0 else 0.0,
                "predictions": all_predictions # Return full list to the results JSON, pagination handled at API level
            }
            
        results_path = f"{file_path}_results.json"
        with open(results_path, "w") as f:
            json.dump(out_results, f)

        dataset.review_status = "Completed"
        dataset.extraction_status = "Complete"
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



