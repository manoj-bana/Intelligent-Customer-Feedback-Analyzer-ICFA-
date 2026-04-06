import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base from models to ensure all models are registered for create_all()
from backend.database.models import Base

# Configuration: Default to local SQLite if no environment variable is provided
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./icfa.db")

# SQLite specific: check_same_thread=False is required for FastAPI concurrency
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Professional Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency generator that yields a database session and ensures it is 
    closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Ensure tables exist at startup
Base.metadata.create_all(bind=engine)

# Seamless migration for existing SQLite DB
try:
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'"))
except Exception:
    # Column likely already exists
    pass