import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router
from backend.routes.data_upload import router as data_upload_router
from backend.routes.admin import router as admin_router
from backend.models.config import CompanyConfig

from backend.database.db import engine
from backend.database.models import Base

# Ensure all tables are created (registered via imports above)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ICFA API")

import logging

# Configure standardized logging for the API
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ICFA")

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info(f"Initialized uploads directory at: {UPLOAD_DIR}")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(data_upload_router, prefix="/ingest", tags=["Ingestion"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": "An unexpected error occurred. Please try again later."},
    )


@app.get("/")
def root():
    return {"message": "ICFA API Running"}

@app.get("/health")
def health():
    return {"status": "ok"}
