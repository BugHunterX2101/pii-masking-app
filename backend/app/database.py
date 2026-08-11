import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

# Load a local .env if present (local dev convenience). Existing environment
# variables always take precedence over the file.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# If no DATABASE_URL is provided (e.g. a fresh Hugging Face Space or quick
# local dev), fall back to a local SQLite file so the app still boots and runs
# end-to-end. The schema layer already supports both dialects (see
# ensure_database_schema in main.py). Point DATABASE_URL at PostgreSQL for
# production/multi-instance deployments.
if not SQLALCHEMY_DATABASE_URL:
    print("[DB] DATABASE_URL not set — using local SQLite fallback (backend/pii_masking.db)")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./pii_masking.db"
    _is_sqlite = True
else:
    _is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
