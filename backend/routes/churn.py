from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io
from backend.utils.churn_model import predict_churn
from backend.database.db import SessionLocal
from backend.database.models import ChurnPrediction

router = APIRouter()

@router.post("/predict")
async def churn_predict(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {e}")

    results = predict_churn(df)

    try:
        db = SessionLocal()
        new_entry = ChurnPrediction(
            user_id=1,
            prediction=str(results)
        )
        db.add(new_entry)
        db.commit()
        db.close()
    except Exception as e:
        print(f"DB save failed (non-critical): {e}")
    
    return results

@router.get("/test")
def test():
    return {"message": "Churn route working!"}
