import sqlite3
import os

def migrate():
    # Get root dir
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    db_path = os.path.join(root_dir, 'icfa.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'security_answers' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN security_answers TEXT')
        print("Added security_answers column.")
    else:
        print("Column already exists.")
    
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
