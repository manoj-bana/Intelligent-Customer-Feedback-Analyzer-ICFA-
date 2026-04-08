import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base from models to ensure all models are registered for create_all()
from backend.database.models import Base

# Configuration: Default to local SQLite if no environment variable is provided
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(ROOT_DIR, "icfa.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{db_path}")

print(f"[DB] Using database at: {db_path}")

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

# --- Auto-migration: add missing columns to existing tables ---
# SQLAlchemy's create_all() does NOT alter existing tables.
# This block ensures new columns are always added on startup.
def _run_migrations():
    """Add any missing columns to existing SQLite tables."""
    if "sqlite" not in DATABASE_URL:
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get current columns in users table
        cursor.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("is_active", "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1"),
            ("role",      "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"),
        ]
        for col_name, sql in migrations:
            if col_name not in existing_cols:
                cursor.execute(sql)
                print(f"[DB] Migration: added '{col_name}' column to users table.")

        # Ensure no users are accidentally locked out (NULL is_active)
        cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")

        conn.commit()
        conn.close()
        print("[DB] Migration check complete.")
    except Exception as e:
        print(f"[DB] Migration warning: {e}")

_run_migrations()