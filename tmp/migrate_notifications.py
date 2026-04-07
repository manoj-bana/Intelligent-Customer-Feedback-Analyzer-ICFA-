import sqlite3
import datetime

db_path = './icfa.db'

print(f"Migrating database: {db_path}...")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the professional notifications table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    
    # Ensure current timestamp logic matches the rest of the app
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT INTO notifications (user_id, message, is_read, created_at) VALUES (?, ?, ?, ?)", 
                   (1, "System: Professional notifications enabled.", 0, now))
    
    conn.commit()
    print("Migration Success: 'notifications' table is now ready!")
    conn.close()
except Exception as e:
    print(f"Migration Error: {e}")
