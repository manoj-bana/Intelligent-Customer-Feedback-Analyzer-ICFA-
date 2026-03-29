import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router
from backend.routes.feedback import router as feedback_router
from backend.routes.churn import router as churn_router
from backend.database.db import engine
from backend.database.models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ICFA API")

# Ensure the uploads directory exists in the root directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,     prefix="/auth",     tags=["Auth"])
app.include_router(feedback_router, prefix="/feedback", tags=["Feedback"])
app.include_router(churn_router,    prefix="/churn",    tags=["Churn"])

@app.get("/")
def root():
    return {"message": "ICFA API Running"}

@app.get("/health")
def health():
    return {"status": "ok"}
