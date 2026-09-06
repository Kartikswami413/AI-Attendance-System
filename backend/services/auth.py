"""
VeriAttend — Authentication Service

JWT token-based authentication for teacher/admin accounts.
Uses bcrypt password hashing (preserved from existing SnapClass).
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from config import settings
from models.database import Teacher, Student, get_db

# OAuth2 scheme for extracting tokens from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(data: dict) -> str:
    """
    Create a JWT access token.

    Args:
        data: payload dict (must include 'sub' key with teacher_id)

    Returns:
        encoded JWT string
    """
    to_encode = data.copy()
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_teacher(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Teacher:
    """
    FastAPI dependency: validates JWT token and returns the current teacher.

    Raises HTTPException 401 if token is invalid or teacher not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        teacher_id = payload.get("sub")
        if teacher_id is None or payload.get("role", "teacher") != "teacher":
            raise credentials_exception
        teacher_id = int(teacher_id)
    except JWTError:
        raise credentials_exception

    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if teacher is None:
        raise credentials_exception

    return teacher


def get_current_student(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Student:
    """Return the authenticated active student; deregistration revokes access."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("role") != "student" or payload.get("sub") is None:
            raise credentials_exception
        student_id = int(payload["sub"])
    except (JWTError, ValueError, TypeError):
        raise credentials_exception
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student or not student.is_active:
        raise credentials_exception
    return student
