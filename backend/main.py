from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.auth import router as auth_router
from backend.routes.ingest import router as ingest_router
from backend.database.db import engine
from backend.database.models import Base

app = FastAPI(title="ICFA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(ingest_router, prefix="/ingest", tags=["Ingestion"])

@app.get("/")
def root():
    return {"message": "ICFA API Running"}

@app.get("/health")
def health():
    return {"status": "ok"}
