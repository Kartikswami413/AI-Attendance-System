"""
VeriAttend — Review Routes

GET  /api/reviews              — List pending manual reviews
POST /api/reviews/{id}/decide  — Approve or reject a review
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from models.database import ManualReview, AttendanceRecord, AttendanceSession, Student, Subject, Teacher, get_db
from models.schemas import ReviewResponse, ReviewDecisionRequest, SuccessResponse
from services.auth import get_current_teacher

router = APIRouter(prefix="/api/reviews", tags=["Manual Reviews"])


@router.get(
    "",
    response_model=list[ReviewResponse],
    summary="List manual review queue",
    description="Get all pending manual reviews for borderline-confidence recognition.",
)
def list_reviews(
    status_filter: str = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get reviews, optionally filtered by status (PENDING, APPROVED, REJECTED)."""
    # Reviewers must only see records belonging to subjects they teach.
    query = (
        db.query(ManualReview)
        .join(AttendanceRecord, ManualReview.attendance_id == AttendanceRecord.attendance_id)
        .join(Subject, AttendanceRecord.subject_id == Subject.subject_id)
        .filter(Subject.teacher_id == teacher.teacher_id)
    )

    if status_filter:
        query = query.filter(ManualReview.status == status_filter.upper())

    reviews = query.order_by(ManualReview.created_at.desc()).all()

    results = []
    for r in reviews:
        student = db.query(Student).filter(Student.student_id == r.student_id).first()
        results.append(ReviewResponse(
            review_id=r.review_id,
            attendance_id=r.attendance_id,
            student_id=r.student_id,
            student_code=student.student_code if student else None,
            student_name=student.name if student else None,
            session_id=r.session_id,
            recognition_confidence=r.recognition_confidence,
            liveness_status=r.liveness_status,
            liveness_score=r.liveness_score,
            status=r.status,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at,
            review_notes=r.review_notes,
            created_at=r.created_at,
        ))

    return results


@router.post(
    "/{review_id}/decide",
    response_model=SuccessResponse,
    summary="Approve or reject a manual review",
    description=(
        "Admin decision on a borderline attendance case. "
        "APPROVED: marks student as present. "
        "REJECTED: marks the attendance as rejected."
    ),
)
def decide_review(
    review_id: int,
    req: ReviewDecisionRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Make a decision on a pending review."""
    if req.decision.upper() not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Decision must be APPROVED or REJECTED.")

    review = (
        db.query(ManualReview)
        .join(AttendanceRecord, ManualReview.attendance_id == AttendanceRecord.attendance_id)
        .join(Subject, AttendanceRecord.subject_id == Subject.subject_id)
        .filter(ManualReview.review_id == review_id, Subject.teacher_id == teacher.teacher_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")

    if review.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Review already {review.status.lower()}.")

    # Update the review
    review.status = req.decision.upper()
    review.reviewed_by = teacher.teacher_id
    review.reviewed_at = datetime.utcnow()
    review.review_notes = req.notes

    # Update the corresponding attendance record
    attendance = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_id == review.attendance_id
    ).first()

    if attendance:
        if req.decision.upper() == "APPROVED":
            attendance.status = "PRESENT"
            attendance.verification_method = "MANUAL_REVIEW"
            attendance.review_status = "APPROVED"
        else:
            attendance.status = "REJECTED"
            attendance.review_status = "REJECTED"

    db.commit()

    action = "approved" if req.decision.upper() == "APPROVED" else "rejected"
    return SuccessResponse(message=f"Review {action} successfully.")
