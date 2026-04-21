import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

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

# Note: We now call create_all in main.py to ensure all models are registered first.
# Base.metadata.create_all(bind=engine)

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

        # 1. Users table migrations
        cursor.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cursor.fetchall()}
        
        user_migrations = [
            ("is_active", "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1"),
            ("role",      "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"),
            ("org_id",    "ALTER TABLE users ADD COLUMN org_id INTEGER"),
            ("security_question", "ALTER TABLE users ADD COLUMN security_question TEXT"),
            ("security_answer_hash", "ALTER TABLE users ADD COLUMN security_answer_hash TEXT"),
            ("reset_token", "ALTER TABLE users ADD COLUMN reset_token TEXT"),
            ("reset_token_expiry", "ALTER TABLE users ADD COLUMN reset_token_expiry TEXT"),
        ]
        for col, sql in user_migrations:
            if col not in user_cols:
                cursor.execute(sql)
                print(f"[DB] Migration: added '{col}' to users.")

        # 2. Datasets table migrations
        cursor.execute("PRAGMA table_info(datasets)")
        ds_cols = {row[1] for row in cursor.fetchall()}
        
        ds_migrations = [
            ("org_id",        "ALTER TABLE datasets ADD COLUMN org_id INTEGER"),
            ("result_data",   "ALTER TABLE datasets ADD COLUMN result_data TEXT"),
            ("error_message", "ALTER TABLE datasets ADD COLUMN error_message TEXT"),
            ("last_analyzed", "ALTER TABLE datasets ADD COLUMN last_analyzed TEXT"),
            ("notification_seen", "ALTER TABLE datasets ADD COLUMN notification_seen INTEGER DEFAULT 0"),
            ("source", "ALTER TABLE datasets ADD COLUMN source TEXT DEFAULT 'web'"),
            ("extraction_status", "ALTER TABLE datasets ADD COLUMN extraction_status TEXT DEFAULT '1 of 1'"),
        ]
        for col, sql in ds_migrations:
            if col not in ds_cols:
                cursor.execute(sql)
                print(f"[DB] Migration: added '{col}' to datasets.")

        # 3. CompanyConfigs table migrations
        cursor.execute("PRAGMA table_info(company_configs)")
        cfg_cols = {row[1] for row in cursor.fetchall()}
        
        cfg_migrations = [
            ("low_risk_threshold", "ALTER TABLE company_configs ADD COLUMN low_risk_threshold FLOAT DEFAULT 0.10"),
            ("churn_prediction_threshold", "ALTER TABLE company_configs ADD COLUMN churn_prediction_threshold FLOAT DEFAULT 0.50"),
        ]
        for col, sql in cfg_migrations:
            if col not in cfg_cols:
                cursor.execute(sql)
                print(f"[DB] Migration: added '{col}' to company_configs.")

        # Ensure no users are locked out
        cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")

        conn.commit()
        conn.close()
        print("[DB] Multi-tenant migration check complete.")
    except Exception as e:
        print(f"[DB] Migration warning: {e}")

_run_migrations()