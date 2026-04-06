import sqlite3
import bcrypt
import os

DB_PATH = "icfa.db"

def hash_value(val: str) -> str:
    if not val: return None
    # If already hashed, skip
    if val.startswith('$2b$'): return val
    return bcrypt.hashpw(val.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- ICFA Database Migration Tool ---")

    # 1. Add missing columns to 'users' table
    columns_to_add = [
        ("reset_token", "TEXT"),
        ("reset_token_expiry", "TEXT")
    ]

    cursor.execute("PRAGMA table_info(users)")
    existing_cols = [col[1] for col in cursor.fetchall()]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            print(f"Adding column: {col_name}...")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        else:
            print(f"Column {col_name} already exists.")

    # 2. Hash existing plain-text passwords and security answers
    cursor.execute("SELECT id, username, password, security_answer_hash FROM users")
    users = cursor.fetchall()

    for user_id, username, password, answer in users:
        updates = []
        params = []

        # Check password
        if password and not password.startswith('$2b$'):
            print(f"Hashing password for user: {username}...")
            new_pass = hash_value(password)
            updates.append("password = ?")
            params.append(new_pass)

        # Check security answer
        if answer and not answer.startswith('$2b$'):
            print(f"Hashing security answer for user: {username}...")
            # Normalize for security answers (lowercase + strip)
            new_answer = hash_value(answer.strip().lower())
            updates.append("security_answer_hash = ?")
            params.append(new_answer)

        if updates:
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            params.append(user_id)
            cursor.execute(query, params)

    conn.commit()
    conn.close()
    print("--- Migration Completed Successfully ---")

if __name__ == "__main__":
    migrate()
