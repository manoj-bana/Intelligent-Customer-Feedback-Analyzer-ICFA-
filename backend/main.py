import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router
from backend.routes.ingest import router as ingest_router
from backend.routes.admin import router as admin_router

from backend.database.db import engine
from backend.database.models import Base

app = FastAPI(title="ICFA API")

import logging

# Configure standardized logging for the API
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ICFA")

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info(f"Initialized uploads directory at: {UPLOAD_DIR}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # TODO: Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(ingest_router, prefix="/ingest", tags=["Ingestion"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])


@app.get("/")
def root():
    return {"message": "ICFA API Running"}

@app.get("/health")
def health():
    return {"status": "ok"}
