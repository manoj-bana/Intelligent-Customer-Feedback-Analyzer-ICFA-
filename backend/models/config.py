from sqlalchemy import Column, Integer, Float, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.database.db import Base

class CompanyConfig(Base):
    """
    Unified configuration table for multi-tenant settings.
    """
    __tablename__ = "company_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), unique=True)
    
    # Sentiment Settings
    pos_threshold = Column(Float, default=0.05)
    neg_threshold = Column(Float, default=-0.05)
    pos_label = Column(String, default="Positive")
    neg_label = Column(String, default="Negative")
    neu_label = Column(String, default="Neutral")
    keyword_boosters = Column(String, nullable=True) # Comma-separated or JSON
    
    # Churn Settings
    high_risk_threshold = Column(Float, default=0.70)
    medium_risk_threshold = Column(Float, default=0.40)
    low_risk_threshold = Column(Float, default=0.10)
    churn_prediction_threshold = Column(Float, default=0.50)
    churn_rules = Column(JSON, nullable=True) # Logic rules for predictability
    
    # Mapping Settings
    column_mapper = Column(JSON, nullable=True) 
    
    organization = relationship("backend.database.models.Organization", back_populates="config")
