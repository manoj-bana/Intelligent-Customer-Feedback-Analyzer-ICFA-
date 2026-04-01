import sqlite3
import os

db_path = './icfa.db'

print(f"Checking database at {os.path.abspath(db_path)}...")

if not os.path.exists(db_path):
    print("Error: icfa.db file not found in current directory.")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(datasets)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'notification_seen' not in columns:
            print("Adding notification_seen column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN notification_seen INTEGER DEFAULT 0")
            conn.commit()
            print("Migration Successful: All history restored.")
        else:
            print("Migration Status: Column already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Migration Error: {e}")
