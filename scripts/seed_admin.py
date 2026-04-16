import os
import bcrypt
import sys
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add the project root to sys.path so we can import backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal, engine, Base
from backend.database.models import User, Organization

load_dotenv()

def hash_password(password: str) -> str:
    """Securely hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed_admin():
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print("Error: ADMIN_EMAIL and ADMIN_PASSWORD must be set in .env")
        return

    # Ensure tables exist
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.role == "admin").first()
        if existing_admin:
            print(f"Admin already exists: {existing_admin.username} ({existing_admin.email})")
            return

        # Check if username 'admin' is taken
        user_with_admin_name = db.query(User).filter(User.username == "admin").first()
        if user_with_admin_name:
            print(f"Found existing user '{user_with_admin_name.username}'. Promoting to Admin role...")
            user_with_admin_name.role = "admin"
            user_with_admin_name.email = admin_email
            user_with_admin_name.password = hash_password(admin_password)
            db.commit()
            print("Successfully promoted existing 'admin' user to Admin role.")
            return

        # Create Default Organization if none exists
        default_org = db.query(Organization).filter(Organization.name == "Default Organization").first()
        if not default_org:
            default_org = Organization(name="Default Organization")
            db.add(default_org)
            db.flush() # Get the ID

        new_admin = User(
            username="admin",
            email=admin_email,
            password=hash_password(admin_password),
            role="admin",
            org_id=default_org.id,
            is_active=1
        )
        db.add(new_admin)
        db.commit()
        print(f"Admin user created successfully: admin / {admin_email} (Org: {default_org.name})")
    except Exception as e:
        print(f"Error seeding admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
