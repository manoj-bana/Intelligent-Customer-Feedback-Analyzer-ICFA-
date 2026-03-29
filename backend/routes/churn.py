from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import pandas as pd
import io
import json
from backend.utils.churn_model import predict_churn
from backend.database.db import SessionLocal
from backend.database.models import ChurnPrediction

import os
import uuid
import shutil

router = APIRouter()

MAX_FILE_SIZE = 100 * 1024 * 1024
churn_jobs = {}

def process_churn_background(job_id: str, file_path: str):
    """
    Background worker function that reads the saved CSV file in chunks
    and processes it for churn prediction without blocking the API thread.
    """
    total_customers_all = 0
    predicted_churn_all = 0
    predictions_sample = [] # Keep a sample for the API response

    try:
        db = SessionLocal()
        # Process the CSV in parts (chunking) to ensure low memory usage
        for chunk in pd.read_csv(file_path, chunksize=1000):
            results = predict_churn(chunk)
            
            if "error" in results:
                raise ValueError(results["error"])

            total_customers_all += results["total_customers"]
            predicted_churn_all += results["predicted_churn"]
            
            if len(predictions_sample) < 100:
                predictions_sample.extend(results["predictions"][:100 - len(predictions_sample)])
            
            try:
                # Add individual entries from the chunk asynchronously to limit memory
                # instead of converting the entire results dict to a string
                db_entries = []
                for pred in results.get("predictions", []):
                    # We store it as a clean JSON string for the specific prediction
                    db_entries.append(ChurnPrediction(
                        user_id=1,
                        prediction=json.dumps(pred)
                    ))
                db.add_all(db_entries)
                db.commit()
            except Exception as e:
                print(f"DB save failed (non-critical): {e}")

            churn_jobs[job_id]["progress"] = f"Processed {total_customers_all} customers so far..."

        db.close()
        
        churn_rate = round((predicted_churn_all / total_customers_all) * 100, 2) if total_customers_all > 0 else 0
        
        churn_jobs[job_id]["status"] = "completed"
        churn_jobs[job_id]["result"] = {
            "total_customers": total_customers_all,
            "predicted_churn": predicted_churn_all,
            "churn_rate": churn_rate,
            "predictions": predictions_sample
        }

    except Exception as e:
        churn_jobs[job_id]["status"] = "failed"
        churn_jobs[job_id]["error"] = str(e)

    # File is now kept in uploads/ as per user request

@router.post("/predict")
async def churn_predict(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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
    churn_jobs[job_id] = {"status": "processing"}
    background_tasks.add_task(process_churn_background, job_id, file_path)

    return {
        "status": "accepted", 
        "message": "File is being processed in the background.", 
        "job_id": job_id
    }

@router.get("/result/{job_id}")
def get_churn_result(job_id: str):
    job = churn_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] == "processing":
        return {"status": "processing", "message": job.get("progress", "Initializing churn models...")}
    
    if job["status"] == "failed":
        return {"status": "failed", "error": job["error"]}
        
    return {"status": "completed", "data": job["result"]}

@router.get("/test")
def test():
    return {"message": "Churn route working!"}
