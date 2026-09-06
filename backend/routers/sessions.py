"""
VeriAttend — Session Routes

POST /api/sessions             — Create a new attendance session
GET  /api/sessions             — List sessions (with filtering)
GET  /api/sessions/{id}        — Get session details
PUT  /api/sessions/{id}/toggle — Activate/deactivate a session
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from models.database import AttendanceSession, Subject, Teacher, get_db
from models.schemas import (
    SessionCreateRequest, SessionResponse, SessionToggleRequest,
    SuccessResponse, ErrorResponse,
)
from services.auth import get_current_teacher

router = APIRouter(prefix="/api/sessions", tags=["Attendance Sessions"])


def _to_local_naive(value: str) -> datetime:
    """Parse a browser timestamp into the local, timezone-neutral SQLite format."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new attendance session",
    description=(
        "Creates a time-bounded attendance session for a subject. "
        "Students can only be marked present during an active session."
    ),
)
def create_session(
    req: SessionCreateRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: DBSession = Depends(get_db),
):
    """Create a new attendance session."""
    # Verify subject exists and belongs to this teacher
    subject = db.query(Subject).filter(
        Subject.subject_id == req.subject_id,
        Subject.teacher_id == teacher.teacher_id,
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or not owned by you.")

    try:
        start_dt = _to_local_naive(req.start_time)
        end_dt = _to_local_naive(req.end_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format.")

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="End time must be after start time.")

    session = AttendanceSession(
        name=req.name,
        subject_id=req.subject_id,
        date=req.date,
        start_time=start_dt,
        end_time=end_dt,
        is_active=True,
        created_by=teacher.teacher_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionResponse(
        session_id=session.session_id,
        name=session.name,
        subject_id=session.subject_id,
        subject_name=subject.name,
        date=session.date,
        start_time=session.start_time,
        end_time=session.end_time,
        is_active=session.is_active,
        created_at=session.created_at,
    )


@router.get(
    "/active",
    response_model=list[SessionResponse],
    summary="List all active sessions (public, no auth required)",
    description=(
        "Public endpoint for students to see which sessions are open for attendance. "
        "No authentication required."
    ),
)
def list_active_sessions(db: DBSession = Depends(get_db)):
    """List all currently active sessions — no auth required."""
    now = datetime.now()
    sessions = (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.is_active.is_(True), AttendanceSession.is_deleted.is_(False),
            AttendanceSession.start_time <= now,
            AttendanceSession.end_time >= now,
        )
        .order_by(AttendanceSession.created_at.desc())
        .all()
    )

    results = []
    for s in sessions:
        subject = db.query(Subject).filter(Subject.subject_id == s.subject_id).first()
        results.append(SessionResponse(
            session_id=s.session_id,
            name=s.name,
            subject_id=s.subject_id,
            subject_name=subject.name if subject else None,
            date=s.date,
            start_time=s.start_time,
            end_time=s.end_time,
            is_active=s.is_active,
            created_at=s.created_at,
        ))

    return results


@router.get(
    "",
    response_model=list[SessionResponse],
    summary="List attendance sessions",
)
def list_sessions(
    subject_id: int = None,
    active_only: bool = False,
    teacher: Teacher = Depends(get_current_teacher),
    db: DBSession = Depends(get_db),
):
    """List sessions, optionally filtered by subject and active status."""
    query = db.query(AttendanceSession).filter(
        AttendanceSession.created_by == teacher.teacher_id,
        AttendanceSession.is_deleted.is_(False),
    )

    if subject_id:
        query = query.filter(AttendanceSession.subject_id == subject_id)
    if active_only:
        query = query.filter(AttendanceSession.is_active == True)

    sessions = query.order_by(AttendanceSession.created_at.desc()).all()

    results = []
    for s in sessions:
        subject = db.query(Subject).filter(Subject.subject_id == s.subject_id).first()
        results.append(SessionResponse(
            session_id=s.session_id,
            name=s.name,
            subject_id=s.subject_id,
            subject_name=subject.name if subject else None,
            date=s.date,
            start_time=s.start_time,
            end_time=s.end_time,
            is_active=s.is_active,
            created_at=s.created_at,
        ))

    return results


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session details",
)
def get_session(session_id: int, db: DBSession = Depends(get_db)):
    """Get details for a specific session."""
    session = db.query(AttendanceSession).filter(
        AttendanceSession.session_id == session_id, AttendanceSession.is_deleted.is_(False)
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    subject = db.query(Subject).filter(Subject.subject_id == session.subject_id).first()

    return SessionResponse(
        session_id=session.session_id,
        name=session.name,
        subject_id=session.subject_id,
        subject_name=subject.name if subject else None,
        date=session.date,
        start_time=session.start_time,
        end_time=session.end_time,
        is_active=session.is_active,
        created_at=session.created_at,
    )


@router.put(
    "/{session_id}/toggle",
    response_model=SuccessResponse,
    summary="Activate or deactivate a session",
)
def toggle_session(
    session_id: int,
    req: SessionToggleRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: DBSession = Depends(get_db),
):
    """Toggle a session's active status."""
    session = db.query(AttendanceSession).filter(
        AttendanceSession.session_id == session_id,
        AttendanceSession.created_by == teacher.teacher_id, AttendanceSession.is_deleted.is_(False),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.is_active = req.is_active
    db.commit()

    status_text = "activated" if req.is_active else "deactivated"
    return SuccessResponse(message=f"Session {status_text} successfully.")


@router.delete("/{session_id}", response_model=SuccessResponse, summary="Archive an attendance session")
def delete_session(session_id: int, teacher: Teacher = Depends(get_current_teacher), db: DBSession = Depends(get_db)):
    """Hide an old session without deleting associated attendance history."""
    session = db.query(AttendanceSession).filter(
        AttendanceSession.session_id == session_id,
        AttendanceSession.created_by == teacher.teacher_id,
        AttendanceSession.is_deleted.is_(False),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    session.is_active = False
    session.is_deleted = True
    session.deleted_at = datetime.utcnow()
    db.commit()
    return SuccessResponse(message="Session deleted from the active list; attendance history was retained.")
