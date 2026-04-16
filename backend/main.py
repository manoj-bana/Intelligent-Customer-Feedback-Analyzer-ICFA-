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


# Startup-time enforcement for SECRET_KEY
@app.on_event("startup")
def enforce_secret_key():
        """Ensure a SECRET_KEY is available for JWT signing.

        Behavior:
        - If REQUIRE_SECRET_KEY is set to 'true' (case-insensitive), the server will
            raise RuntimeError on startup when SECRET_KEY is missing. This is the
            strict production mode.
        - Otherwise (default), if SECRET_KEY is missing we'll generate an
            ephemeral one for development and log a warning. Tokens signed with this
            key will be invalidated on process restart.
        """
        require = os.getenv("REQUIRE_SECRET_KEY", "false").lower() == "true"
        from backend.auth import SECRET_KEY as _secret  # refer to module-level value

        if not _secret:
                if require:
                        # Fail early in production if a secret isn't configured
                        logger.critical("SECRET_KEY missing and REQUIRE_SECRET_KEY=true; aborting startup.")
                        raise RuntimeError("CRITICAL: SECRET_KEY must be set in environment before starting the server.")
                else:
                        # Development-friendly: generate ephemeral secret and set in module
                        import secrets as _secrets
                        gen = _secrets.token_urlsafe(64)
                        try:
                                # Mutate backend.auth.SECRET_KEY so subsequent imports use it
                                import importlib
                                auth_mod = importlib.import_module('backend.auth')
                                setattr(auth_mod, 'SECRET_KEY', gen)
                                logger.warning("No SECRET_KEY found. Generated ephemeral SECRET_KEY for development."
                                                             " Set SECRET_KEY in .env for persistent tokens.")
                        except Exception:
                                logger.exception("Failed to set ephemeral SECRET_KEY on backend.auth module.")

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
