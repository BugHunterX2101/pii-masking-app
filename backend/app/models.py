from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import uuid

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True)
    plan = Column(String, default="free")
    created_at = Column(DateTime, default=datetime.utcnow)

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: f"pk_{uuid.uuid4().hex}")
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, default="Default Key")
    key_hash = Column(String, nullable=False) # Store securely
    rate_limit = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)  # 'admin' or 'user'
    is_active = Column(Boolean, default=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True) # nullable for legacy support during migration

    organization = relationship("Organization")

class DLPPolicy(Base):
    __tablename__ = "dlp_policies"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    pii_type = Column(String, index=True, nullable=False) # Removed unique=True to allow same policy type per org
    is_active = Column(Boolean, default=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # can be null if called via API Key
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)
    action = Column(String, nullable=False) # e.g., "MASK_IMAGE", "MASK_TEXT", "LOGIN"
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String, nullable=True)
    details = Column(JSON, nullable=True) # JSON containing what was detected, etc.

    user = relationship("User")
    organization = relationship("Organization")

class CustomRegexPolicy(Base):
    __tablename__ = "custom_regex_policies"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    name = Column(String, index=True, nullable=False) # Removed unique=True
    pattern = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    masking_style = Column(String, default="LABEL", nullable=False) # LABEL, BLACKOUT, ASTERISK
