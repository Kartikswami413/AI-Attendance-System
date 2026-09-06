"""
VeriAttend — Admin Routes

GET  /api/admin/dashboard     — Dashboard statistics
POST /api/admin/subjects      — Create a subject
GET  /api/admin/subjects      — List teacher's subjects
GET  /api/admin/attendance    — Get detailed attendance report
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from models.database import (
    Teacher, Student, Subject, SubjectStudent,
    AttendanceRecord, AttendanceSession, ManualReview, get_db,
)
from models.schemas import (
    DashboardStats, SubjectCreateRequest, SubjectResponse,
    AttendanceRecordResponse, SuccessResponse,
)
from services.auth import get_current_teacher

router = APIRouter(prefix="/api/admin", tags=["Admin Dashboard"])


@router.get(
    "/dashboard",
    response_model=DashboardStats,
    summary="Get dashboard statistics",
    description="Returns aggregate statistics for the admin dashboard.",
)
def get_dashboard_stats(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get overview statistics for the admin dashboard."""
    today = datetime.now().strftime("%Y-%m-%d")

    teacher_subject_ids = [
        row[0] for row in db.query(Subject.subject_id).filter(
            Subject.teacher_id == teacher.teacher_id
        ).all()
    ]
    enrolled_student_ids = [
        row[0] for row in db.query(SubjectStudent.student_id).filter(
            SubjectStudent.subject_id.in_(teacher_subject_ids)
        ).distinct().all()
    ]
    total_students = len(enrolled_student_ids)

    # Students marked present today
    present_today = db.query(AttendanceRecord.student_id).filter(
        AttendanceRecord.subject_id.in_(teacher_subject_ids),
        AttendanceRecord.date == today,
        AttendanceRecord.status == "PRESENT",
    ).distinct().count()

    # Students with face embeddings but not present today
    enrolled_students_with_face = db.query(Student).filter(
        Student.student_id.in_(enrolled_student_ids),
        Student.face_embedding.isnot(None)
    ).count()
    absent_today = max(0, enrolled_students_with_face - present_today)

    pending_reviews = db.query(ManualReview).join(
        AttendanceRecord, ManualReview.attendance_id == AttendanceRecord.attendance_id
    ).filter(
        ManualReview.status == "PENDING",
        AttendanceRecord.subject_id.in_(teacher_subject_ids),
    ).count()

    total_sessions = db.query(AttendanceSession).filter(
        AttendanceSession.created_by == teacher.teacher_id
    ).count()

    return DashboardStats(
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        pending_reviews=pending_reviews,
        total_sessions=total_sessions,
    )


@router.post(
    "/subjects",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subject",
)
def create_subject(
    req: SubjectCreateRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Create a new subject/course for this teacher."""
    existing = db.query(Subject).filter(Subject.subject_code == req.subject_code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Subject code '{req.subject_code}' already exists.")

    subject = Subject(
        subject_code=req.subject_code,
        name=req.name,
        section=req.section,
        teacher_id=teacher.teacher_id,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    return SubjectResponse(
        subject_id=subject.subject_id,
        subject_code=subject.subject_code,
        name=subject.name,
        section=subject.section,
        teacher_id=subject.teacher_id,
        enrolled_count=0,
        created_at=subject.created_at,
    )


@router.get(
    "/subjects",
    response_model=list[SubjectResponse],
    summary="List teacher's subjects",
)
def list_subjects(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get all subjects belonging to the authenticated teacher."""
    subjects = db.query(Subject).filter(
        Subject.teacher_id == teacher.teacher_id
    ).all()

    results = []
    for s in subjects:
        count = db.query(SubjectStudent).filter(
            SubjectStudent.subject_id == s.subject_id
        ).count()

        results.append(SubjectResponse(
            subject_id=s.subject_id,
            subject_code=s.subject_code,
            name=s.name,
            section=s.section,
            teacher_id=s.teacher_id,
            enrolled_count=count,
            created_at=s.created_at,
        ))

    return results


@router.get(
    "/attendance",
    response_model=list[AttendanceRecordResponse],
    summary="Get detailed attendance report",
    description="Filterable attendance report for admin dashboard.",
)
def get_attendance_report(
    subject_id: int = None,
    session_id: int = None,
    date: str = None,
    student_name: str = None,
    status_filter: str = None,
    limit: int = 200,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get attendance records for admin dashboard with filtering."""
    # Only show records for teacher's subjects
    teacher_subject_ids = [
        s.subject_id for s in
        db.query(Subject).filter(Subject.teacher_id == teacher.teacher_id).all()
    ]

    query = db.query(AttendanceRecord).filter(
        AttendanceRecord.subject_id.in_(teacher_subject_ids)
    )

    if subject_id:
        query = query.filter(AttendanceRecord.subject_id == subject_id)
    if session_id:
        query = query.filter(AttendanceRecord.session_id == session_id)
    if date:
        query = query.filter(AttendanceRecord.date == date)
    if status_filter:
        query = query.filter(AttendanceRecord.status == status_filter.upper())

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit).all()

    results = []
    for r in records:
        student = db.query(Student).filter(Student.student_id == r.student_id).first()
        subject = db.query(Subject).filter(Subject.subject_id == r.subject_id).first()

        # Filter by student name if provided
        if student_name and student:
            if student_name.lower() not in student.name.lower():
                continue

        results.append(AttendanceRecordResponse(
            attendance_id=r.attendance_id,
            student_id=r.student_id,
            student_code=student.student_code if student else None,
            student_name=student.name if student else None,
            subject_id=r.subject_id,
            subject_name=subject.name if subject else None,
            session_id=r.session_id,
            date=r.date,
            timestamp=r.timestamp,
            recognition_confidence=r.recognition_confidence,
            liveness_score=r.liveness_score,
            liveness_status=r.liveness_status,
            status=r.status,
            verification_method=r.verification_method,
            review_status=r.review_status,
        ))

    return results
