from backend.database.db import engine, SessionLocal
from sqlalchemy import text

def migrate():
    print("Checking for churn_prediction_threshold column...")
    try:
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(company_configs)"))
            columns = [row[1] for row in result]
            
            if "churn_prediction_threshold" not in columns:
                print("Adding churn_prediction_threshold column...")
                conn.execute(text("ALTER TABLE company_configs ADD COLUMN churn_prediction_threshold FLOAT DEFAULT 0.50"))
                conn.commit()
                print("Column added successfully.")
            else:
                print("Column already exists.")
                
            if "low_risk_threshold" not in columns:
                print("Adding low_risk_threshold column...")
                conn.execute(text("ALTER TABLE company_configs ADD COLUMN low_risk_threshold FLOAT DEFAULT 0.10"))
                conn.commit()
                print("Column added successfully.")
                
    except Exception as e:
        print(f"Migration error: {e}")

if __name__ == "__main__":
    migrate()
