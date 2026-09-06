"""
Database configuration — Local SQLite via SQLAlchemy.

Uses the same veriattend.db as the FastAPI backend so both
the Streamlit app and the backend share one database.
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the backend directory to sys.path so we can import its models
_backend_dir = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, "backend"
)
_backend_dir = os.path.abspath(_backend_dir)

if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Path to the shared SQLite database
_db_path = os.path.join(_backend_dir, "veriattend.db")
DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Get a new database session. Caller must close it."""
    return SessionLocal()