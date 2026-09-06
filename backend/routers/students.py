"""
VeriAttend — Student Routes

POST /api/students           — Register a new student
GET  /api/students           — List all students
GET  /api/students/{id}      — Get student by ID
PUT  /api/students/{id}      — Update student profile
POST /api/students/{id}/enroll-face — Enroll/re-enroll face embedding
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import numpy as np
import base64
import cv2
import logging

from models.database import Student, SubjectStudent, get_db
from models.schemas import (
    StudentRegisterRequest, StudentResponse, StudentUpdateRequest,
    EnrollFaceRequest, EnrollFaceResponse, ErrorResponse, SuccessResponse,
    StudentLoginRequest, StudentTokenResponse, DeregisterStudentRequest,
)
from services.face_detection import detect_faces, get_face_landmarks, compute_face_embedding
from services.face_recognition_service import invalidate_classifier_cache
from services.auth import hash_password, verify_password, create_access_token, get_current_student

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/students", tags=["Students"])


def _student_response(student: Student) -> StudentResponse:
    """Keep active/deregistered status visible in admin and profile responses."""
    active = bool(student.is_active)
    return StudentResponse(
        student_id=student.student_id, student_code=student.student_code,
        name=student.name, email=student.email, department=student.department,
        year=student.year, has_face_embedding=student.face_embedding is not None,
        is_active=active, account_status="Active" if active else "Deregistered",
        created_at=student.created_at,
    )


def _decode_frame(frame_data: str) -> np.ndarray:
    """Decode a base64-encoded image to numpy RGB array."""
    # Handle data URI prefix
    if "," in frame_data:
        frame_data = frame_data.split(",", 1)[1]

    img_bytes = base64.b64decode(frame_data)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@router.post(
    "",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student",
    responses={409: {"model": ErrorResponse, "description": "Student ID already exists"}},
)
def register_student(req: StudentRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new student with their details.
    Face enrollment is done separately via the enroll-face endpoint.
    """
    # Prevent duplicate student codes
    student_code = req.student_code.strip()
    email = req.email.strip().lower() if req.email and req.email.strip() else None

    existing = db.query(Student).filter(Student.student_code == student_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student ID '{student_code}' already exists.",
        )

    if email and db.query(Student).filter(Student.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already registered to another student.",
        )

    student = Student(
        student_code=student_code,
        name=req.name.strip(),
        email=email,
        department=req.department.strip() if req.department and req.department.strip() else None,
        year=req.year.strip() if req.year and req.year.strip() else None,
        password_hash=hash_password(req.password) if req.password else None,
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this ID or email address already exists.",
        )
    db.refresh(student)

    return _student_response(student)


@router.post("/login", response_model=StudentTokenResponse, summary="Student account login")
def login_student(req: StudentLoginRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.student_code == req.student_code.strip()).first()
    if not student or not student.password_hash or not verify_password(req.password, student.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid student ID or password.")
    if not student.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This student account has been deregistered.")
    return StudentTokenResponse(
        access_token=create_access_token(data={"sub": str(student.student_id), "role": "student"}),
        student_id=student.student_id, name=student.name,
    )


@router.get("/me", response_model=StudentResponse, summary="Get the current student profile")
def get_my_profile(student: Student = Depends(get_current_student)):
    return _student_response(student)


@router.delete("/me", response_model=SuccessResponse, summary="Deregister the current student account")
def deregister_my_account(
    req: DeregisterStudentRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Soft-deactivate only the caller, retaining reportable attendance history."""
    if req.confirmation.strip().upper() != "DEREGISTER":
        raise HTTPException(status_code=400, detail="Type DEREGISTER to confirm account removal.")
    if not verify_password(req.password, student.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password confirmation is incorrect.")
    # Delete only active associations/biometrics. Attendance and review FKs stay intact.
    db.query(SubjectStudent).filter(SubjectStudent.student_id == student.student_id).delete()
    student.face_embedding = None
    student.voice_embedding = None
    student.is_active = False
    from datetime import datetime
    student.deregistered_at = datetime.utcnow()
    db.commit()
    invalidate_classifier_cache()
    logger.info("Student %s deregistered their account", student.student_id)
    return SuccessResponse(message="Account deregistered. Attendance history has been retained for reports.")


@router.get(
    "",
    response_model=list[StudentResponse],
    summary="List all registered students",
)
def list_students(db: Session = Depends(get_db)):
    """Get all registered students."""
    students = db.query(Student).all()
    return [_student_response(s) for s in students]


@router.get(
    "/{student_id}",
    response_model=StudentResponse,
    summary="Get a student by ID",
    responses={404: {"model": ErrorResponse}},
)
def get_student(student_id: int, db: Session = Depends(get_db)):
    """Get a specific student's profile."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    return _student_response(student)


@router.put(
    "/{student_id}",
    response_model=StudentResponse,
    summary="Update student profile",
    responses={404: {"model": ErrorResponse}},
)
def update_student(student_id: int, req: StudentUpdateRequest, db: Session = Depends(get_db)):
    """Update student profile fields."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    # `model_fields_set` distinguishes an omitted field from an explicit null,
    # allowing an optional value such as email to be deliberately cleared.
    fields_set = req.model_fields_set
    if "name" in fields_set and req.name is not None:
        student.name = req.name.strip()
    if "email" in fields_set:
        email = req.email.strip().lower() if req.email and req.email.strip() else None
        if email:
            email_owner = db.query(Student).filter(
                Student.email == email,
                Student.student_id != student_id,
            ).first()
            if email_owner:
                raise HTTPException(status_code=409, detail="This email address is already registered to another student.")
        student.email = email
    if "department" in fields_set:
        student.department = req.department.strip() if req.department and req.department.strip() else None
    if "year" in fields_set:
        student.year = req.year.strip() if req.year and req.year.strip() else None

    db.commit()
    db.refresh(student)

    return _student_response(student)


@router.post(
    "/{student_id}/enroll-face",
    response_model=EnrollFaceResponse,
    summary="Enroll or re-enroll a student's face",
    description=(
        "Captures a face from the provided image frame, validates that exactly one face "
        "is present, generates a 128D embedding, and stores it for the student. "
        "Can be used for initial enrollment or re-enrollment."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image or multiple faces"},
        404: {"model": ErrorResponse, "description": "Student not found"},
    },
)
def enroll_face(student_id: int, req: EnrollFaceRequest, db: Session = Depends(get_db)):
    """
    Enroll a student's face from a camera frame.

    Workflow:
        1. Decode the base64 image
        2. Detect faces — reject if 0 or >1 faces
        3. Check image quality
        4. Extract 68-point landmarks
        5. Compute 128D face embedding
        6. Store embedding (overwrites previous if re-enrolling)
        7. Invalidate classifier cache
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    if not student.is_active:
        raise HTTPException(status_code=403, detail="Deregistered students cannot enroll biometric data.")

    # Decode frame
    try:
        image_np = _decode_frame(req.frame_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {str(e)}")

    # Detect faces
    detection = detect_faces(image_np)

    if detection["status"] == "NO_FACE":
        raise HTTPException(status_code=400, detail="No face detected in the image.")
    if detection["status"] == "MULTIPLE_FACES":
        raise HTTPException(
            status_code=400,
            detail=f"Multiple faces detected ({detection['num_faces']}). Please capture with only one face.",
        )
    if detection["status"] == "LOW_QUALITY":
        raise HTTPException(status_code=400, detail="Image quality too low. Please try again.")

    # Get landmarks and compute embedding
    face_rect = detection["faces"][0]
    landmarks = get_face_landmarks(image_np, face_rect)
    embedding = compute_face_embedding(image_np, landmarks)

    # Store embedding (as list of floats)
    student.face_embedding = embedding.tolist()
    db.commit()

    # Invalidate classifier cache so it rebuilds with new embedding
    invalidate_classifier_cache()

    logger.info(f"Face enrolled for student {student.student_code} (id={student_id})")

    return EnrollFaceResponse(
        success=True,
        message="Face enrolled successfully.",
        student_id=student_id,
    )
