"""
VeriAttend — Enrollment Routes

POST /api/enrollment/enroll        — Enroll student in a subject
DELETE /api/enrollment/unenroll    — Unenroll student from a subject
GET  /api/enrollment/{subject_id}  — Get enrolled students for a subject
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.database import Subject, Student, SubjectStudent, Teacher, get_db
from models.schemas import SubjectEnrollRequest, SuccessResponse, ErrorResponse
from services.auth import get_current_teacher

router = APIRouter(prefix="/api/enrollment", tags=["Enrollment"])


@router.post(
    "/enroll",
    response_model=SuccessResponse,
    summary="Enroll a student in a subject",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Already enrolled"},
    },
)
def enroll_student(
    req: SubjectEnrollRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Enroll a student in a subject using the subject code."""
    # Find subject by code
    subject = db.query(Subject).filter(
        Subject.subject_code == req.subject_code,
        Subject.teacher_id == teacher.teacher_id,
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject with code '{req.subject_code}' not found.")

    # Check student exists
    student = db.query(Student).filter(Student.student_id == req.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    if not student.is_active:
        raise HTTPException(status_code=403, detail="Deregistered students cannot be enrolled in subjects.")

    # Check already enrolled
    existing = db.query(SubjectStudent).filter(
        SubjectStudent.subject_id == subject.subject_id,
        SubjectStudent.student_id == req.student_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Student is already enrolled in this subject.")

    enrollment = SubjectStudent(
        subject_id=subject.subject_id,
        student_id=req.student_id,
    )
    db.add(enrollment)
    db.commit()

    return SuccessResponse(message=f"Enrolled in {subject.name} successfully.")


@router.delete(
    "/unenroll",
    response_model=SuccessResponse,
    summary="Unenroll a student from a subject",
)
def unenroll_student(
    student_id: int,
    subject_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Remove a student's enrollment from a subject."""
    subject = db.query(Subject).filter(
        Subject.subject_id == subject_id,
        Subject.teacher_id == teacher.teacher_id,
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or not managed by you.")
    enrollment = db.query(SubjectStudent).filter(
        SubjectStudent.subject_id == subject_id,
        SubjectStudent.student_id == student_id,
    ).first()

    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found.")

    db.delete(enrollment)
    db.commit()

    return SuccessResponse(message="Unenrolled successfully.")


@router.get(
    "/{subject_id}/students",
    summary="Get all students enrolled in a subject",
)
def get_enrolled_students(
    subject_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """List all students enrolled in a specific subject."""
    subject = db.query(Subject).filter(
        Subject.subject_id == subject_id,
        Subject.teacher_id == teacher.teacher_id,
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    enrollments = db.query(SubjectStudent).filter(
        SubjectStudent.subject_id == subject_id
    ).all()

    students = []
    for e in enrollments:
        student = db.query(Student).filter(Student.student_id == e.student_id).first()
        if student:
            students.append({
                "student_id": student.student_id,
                "student_code": student.student_code,
                "name": student.name,
                "has_face_embedding": student.face_embedding is not None,
                "is_active": student.is_active,
                "account_status": "Active" if student.is_active else "Deregistered",
                "enrolled_at": str(e.enrolled_at) if e.enrolled_at else None,
            })

    return students
