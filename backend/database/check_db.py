from backend.database.db import SessionLocal
from backend.database.models import User

db = SessionLocal()

users = db.query(User).all()

for user in users:
    print(user.id, user.username, user.email)