from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    password = Column(String)
<<<<<<< HEAD
    security_question = Column(String, nullable=True)
    security_answer_hash = Column(String, nullable=True)
=======
>>>>>>> 14f205fd958a5f5136b66e59389e3083bbfdb9f6


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)  
    text = Column(String)
    sentiment = Column(String)
    created_at = Column(String, default=str(datetime.datetime.utcnow()))


class ChurnPrediction(Base):
    __tablename__ = "churn_predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    prediction = Column(String)
    created_at = Column(String, default=str(datetime.datetime.utcnow()))