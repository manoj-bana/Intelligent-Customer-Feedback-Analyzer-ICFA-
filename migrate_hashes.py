
import sys
import sqlite3
import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./icfa.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


def is_bcrypt(value: str) -> bool:
    return value is not None and (value.startswith("$2b$") or value.startswith("$2a$"))


def add_missing_columns():
    conn = sqlite3.connect("icfa.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    if "reset_token" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_token TEXT")
        print("  Added column: reset_token")

    if "reset_token_expiry" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_token_expiry TEXT")
        print("  Added column: reset_token_expiry")

    conn.commit()
    conn.close()


def migrate():
    db = Session()
    try:
        from backend.database.models import User, Base

        users = db.query(User).all()
        updated = 0

        for user in users:
            changed = False

            if user.password and not is_bcrypt(user.password):
                print(f"  Hashing password for: {user.username}")
                user.password = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
                changed = True

            if user.security_answer_hash and not is_bcrypt(user.security_answer_hash):
                print(f"  Hashing security answer for: {user.username}")
                normalized = user.security_answer_hash.strip().lower()
                user.security_answer_hash = bcrypt.hashpw(normalized.encode(), bcrypt.gensalt()).decode()
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
    add_missing_columns()
    migrate()