from backend.database.db import engine, SessionLocal
from backend.database.models import User
from sqlalchemy import text

def verify():
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(users);")).mappings().all()
        has_role = any(c['name'] == 'role' for c in cols)
        print("Role column exists:", has_role)
        
        if not has_role:
            print("Running migration manually...")
            with engine.begin() as t_conn:
                t_conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'"))
        
verify()
print("Verification complete.")
