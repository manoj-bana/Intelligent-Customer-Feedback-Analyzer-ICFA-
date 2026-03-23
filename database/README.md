# ICFA Database Structure

## SQLite Database Schema

### Tables

#### 1. users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);
```

#### 2. analysis_sessions
```sql
CREATE TABLE analysis_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    session_type TEXT NOT NULL, -- 'sentiment' or 'churn'
    file_name TEXT,
    file_size INTEGER,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'processing', -- 'processing', 'completed', 'failed'
    result_data TEXT, -- JSON stored as TEXT
    metadata TEXT, -- JSON stored as TEXT
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

#### 3. analysis_results
```sql
CREATE TABLE analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    record_id TEXT,
    result_data TEXT, -- JSON stored as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES analysis_sessions (id)
);
```

## Usage

- Store user accounts and authentication data
- Track analysis sessions per user
- Store detailed results for each uploaded file
- Enable session persistence and history
- Support multi-user environment

## Integration Points

- Replace in-memory auth storage in `backend/auth.py`
- Update analysis routes to save results to database
- Add session history to dashboard
- Implement user-specific data isolation