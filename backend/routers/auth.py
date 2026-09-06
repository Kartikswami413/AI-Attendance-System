"""
VeriAttend — Auth Routes

POST /api/auth/register  — Register a new teacher account
POST /api/auth/login     — Login and receive JWT token
GET  /api/auth/me        — Get current teacher info
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.database import Teacher, get_db
from models.schemas import (
    TeacherRegisterRequest, TeacherLoginRequest,
    TokenResponse, TeacherResponse, ErrorResponse,
)
from services.auth import (
    hash_password, verify_password, create_access_token, get_current_teacher,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TeacherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new teacher account",
    responses={409: {"model": ErrorResponse, "description": "Username already taken"}},
)
def register_teacher(req: TeacherRegisterRequest, db: Session = Depends(get_db)):
    """Register a new teacher account with username and password."""
    # Check for duplicate username
    existing = db.query(Teacher).filter(Teacher.username == req.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken.",
        )

    teacher = Teacher(
        username=req.username,
        password_hash=hash_password(req.password),
        name=req.name,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    return teacher


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT token",
    responses={401: {"model": ErrorResponse, "description": "Invalid credentials"}},
)
def login_teacher(req: TeacherLoginRequest, db: Session = Depends(get_db)):
    """Authenticate with username/password and receive a JWT access token."""
    teacher = db.query(Teacher).filter(Teacher.username == req.username).first()
    if not teacher or not verify_password(req.password, teacher.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(data={"sub": str(teacher.teacher_id), "role": "teacher"})

    return TokenResponse(
        access_token=token,
        teacher_id=teacher.teacher_id,
        name=teacher.name,
    )


@router.get(
    "/me",
    response_model=TeacherResponse,
    summary="Get current teacher info",
)
def get_me(teacher: Teacher = Depends(get_current_teacher)):
    """Get the profile of the currently authenticated teacher."""
    return teacher
