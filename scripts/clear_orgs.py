import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal
from backend.database.models import Organization, User, CompanyConfig

def clear_organizations():
    db = SessionLocal()
    try:
        # 1. Clear config settings linked to organizations
        db.query(CompanyConfig).delete()
        
        # 2. Reset users' org_id to None so we don't have broken links
        db.query(User).update({"org_id": None})
        
        # 3. Delete all organizations
        num_deleted = db.query(Organization).delete()
        
        db.commit()
        print(f"Successfully deleted {num_deleted} organizations and cleared related data.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clear_organizations()
