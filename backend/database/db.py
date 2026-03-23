from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base

DATABASE_URL = "sqlite:///./icfa.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(bind=engine)