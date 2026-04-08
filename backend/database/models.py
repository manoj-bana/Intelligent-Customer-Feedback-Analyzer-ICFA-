import datetime
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    """
    Represents a system user with authentication and password-reset attributes.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    password = Column(String)
    role = Column(String, default="user") # user, admin
    is_active = Column(Integer, default=1) # 1 = Active, 0 = Deactivated
    security_question = Column(String, nullable=True)
    security_answer_hash = Column(String, nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expiry = Column(String, nullable=True)

class AdminRequest(Base):
    """
    Tracks user requests for administrative privilege elevation.
    """
    __tablename__ = "admin_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    username = Column(String)
    reason = Column(String)
    status = Column(String, default="pending") # pending, approved, rejected
    created_at = Column(
        String, 
        default=lambda: datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )

class Dataset(Base):
    """
    Stores metadata for uploaded files (Cases), tracking their source, 
    processing status, and associated user.
    """
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True)
    user_id = Column(Integer)
    filename = Column(String)
    file_path = Column(String)
    source = Column(String, default="web")
    review_status = Column(String, default="pending")
    extraction_status = Column(String, default="1 of 1")
    task_type = Column(String)
    created_at = Column(
        String, 
        default=lambda: datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )
    notification_seen = Column(Integer, default=0)

class Feedback(Base):
    """
    Model for individual customer feedback entries and their analyzed sentiment.
    """
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    dataset_id = Column(Integer, nullable=True)
    text = Column(String)
    sentiment = Column(String)
    created_at = Column(
        String, 
        default=lambda: datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )

class ChurnPrediction(Base):
    """
    Model for customer churn prediction results.
    """
    __tablename__ = "churn_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    dataset_id = Column(Integer, nullable=True)
    prediction = Column(String)
    created_at = Column(
        String, 
        default=lambda: datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )

class Notification(Base):
    """
    Dedicated table for professional system notifications (e.g., Progress, Success).
    """
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    message = Column(String)
    is_read = Column(Integer, default=0) # 0 = Unread, 1 = Read
    created_at = Column(
        String, 
        default=lambda: datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )