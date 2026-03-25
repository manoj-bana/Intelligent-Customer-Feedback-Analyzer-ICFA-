"""
migrate_hashes.py
-----------------
Run this ONCE to hash any existing plain-text passwords and security answers
in icfa.db before deploying the enhanced backend.

Usage:
    python migrate_hashes.py

It is safe to run multiple times — already-hashed values are left untouched.
"""

import sys
import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./icfa.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


def is_bcrypt(value: str) -> bool:
    return value is not None and (value.startswith("$2b$") or value.startswith("$2a$"))


def migrate():
    db = Session()
    try:
        # Lazy import so the model changes in models.py are picked up
        from backend.database.models import User, Base
        Base.metadata.create_all(bind=engine)   # add new columns if missing

        users = db.query(User).all()
        updated = 0

        for user in users:
            changed = False

            # Hash password if plain-text
            if user.password and not is_bcrypt(user.password):
                hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
                print(f"  Hashing password for user: {user.username}")
                user.password = hashed
                changed = True

            # Hash security answer if plain-text
            if user.security_answer_hash and not is_bcrypt(user.security_answer_hash):
                normalized = user.security_answer_hash.strip().lower()
                hashed_ans = bcrypt.hashpw(normalized.encode(), bcrypt.gensalt()).decode()
                print(f"  Hashing security answer for user: {user.username}")
                user.security_answer_hash = hashed_ans
                changed = True

            if changed:
                updated += 1

        db.commit()
        print(f"\n✅ Migration complete. {updated} user(s) updated.")
    except Exception as exc:
        db.rollback()
        print(f"❌ Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    print("🔄 Migrating existing users to bcrypt hashes…")
    migrate()
