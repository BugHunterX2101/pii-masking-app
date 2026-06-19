from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)  # 'admin' or 'user'
    is_active = Column(Boolean, default=True)

class DLPPolicy(Base):
    __tablename__ = "dlp_policies"

    id = Column(Integer, primary_key=True, index=True)
    pii_type = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False) # e.g., "MASK_IMAGE", "MASK_TEXT", "LOGIN"
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String, nullable=True)
    details = Column(JSON, nullable=True) # JSON containing what was detected, etc.

    user = relationship("User")
