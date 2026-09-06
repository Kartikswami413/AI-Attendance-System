"""
VeriAttend — Attendance Routes

POST /api/attendance/mark          — Full attendance pipeline (detect → liveness → recognize → decide)
GET  /api/attendance/records       — Get attendance records with filtering
GET  /api/attendance/student/{id}  — Get attendance for a specific student
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import numpy as np
import base64
import cv2
import logging

from models.database import (
    AttendanceRecord, AttendanceSession, ManualReview,
    Student, Subject, get_db,
)
from models.schemas import (
    AttendanceDecision, AttendanceRequest,
    AttendanceRecordResponse, ErrorResponse,
)
from services.face_detection import detect_faces, get_face_landmarks, compute_face_embedding
from services.face_recognition_service import recognize_face
from services.liveness import check_passive_liveness
from services.attendance_decision import AttendanceDecisionInput, make_attendance_decision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


def _decode_frame(frame_data: str) -> np.ndarray:
    """Decode base64 image to numpy RGB array."""
    if "," in frame_data:
        frame_data = frame_data.split(",", 1)[1]
    img_bytes = base64.b64decode(frame_data)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@router.post(
    "/mark",
    response_model=AttendanceDecision,
    summary="Mark attendance via full AI pipeline",
    description=(
        "Complete attendance pipeline:\n"
        "1. Decode camera frame\n"
        "2. Detect face (reject 0 or multiple faces)\n"
        "3. Run passive liveness check\n"
        "4. Recognize face identity\n"
        "5. Make attendance decision based on confidence\n"
        "6. Store attendance record\n"
        "7. Create manual review if borderline"
    ),
)
def mark_attendance(req: AttendanceRequest, db: Session = Depends(get_db)):
    """
    Full attendance marking pipeline.

    This is the main endpoint called during the attendance workflow.
    It combines all verification steps and produces a final decision.
    """
    # Decode frame
    try:
        image_np = _decode_frame(req.frame_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data.")

    # Step 1: Face Detection
    detection = detect_faces(image_np)

    # Step 2: Liveness (passive check on the frame)
    liveness_result = {"liveness": "NOT_CHECKED", "score": 0.0}
    if detection["status"] == "ONE_FACE":
        liveness_result = check_passive_liveness(image_np)

    # Step 3: Recognition (only if one face detected)
    recognition_result = {
        "recognized": False, "student_id": None,
        "student_code": None, "name": None,
        "confidence": 0.0, "distance": float("inf"),
        "message": "Face not detected.",
    }
    if detection["status"] == "ONE_FACE":
        face_rect = detection["faces"][0]
        landmarks = get_face_landmarks(image_np, face_rect)
        embedding = compute_face_embedding(image_np, landmarks)
        recognition_result = recognize_face(embedding, db)

    # Step 4: Decision Engine
    decision_input = AttendanceDecisionInput(
        face_detection_status=detection["status"],
        face_count=detection["num_faces"],
        liveness_status=liveness_result["liveness"],
        liveness_score=liveness_result.get("score", 0.0),
        recognition_result=recognition_result,
        session_id=req.session_id,
        db=db,
    )

    decision = make_attendance_decision(decision_input)

    # Step 5: Persist attendance record (for APPROVED and MANUAL_REVIEW)
    if decision["decision"] in ("APPROVED", "MANUAL_REVIEW") and decision["student_id"]:
        session = db.query(AttendanceSession).filter(
            AttendanceSession.session_id == req.session_id
        ).first()
        # The session date is the source of truth, which also keeps reports correct
        # when a session crosses midnight or the server uses a different timezone.
        attendance_date = session.date if session else datetime.now().strftime("%Y-%m-%d")

        record = AttendanceRecord(
            student_id=decision["student_id"],
            subject_id=session.subject_id if session else 0,
            session_id=req.session_id,
            date=attendance_date,
            timestamp=datetime.now(),
            recognition_confidence=decision["recognition_confidence"],
            liveness_score=decision["liveness_score"],
            liveness_status=decision["liveness_status"],
            status="PRESENT" if decision["decision"] == "APPROVED" else "MANUAL_REVIEW",
            verification_method=(
                "AUTO_HIGH_CONFIDENCE" if decision["decision"] == "APPROVED" else "MANUAL_REVIEW"
            ),
            review_status="APPROVED" if decision["decision"] == "APPROVED" else "PENDING",
        )
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
        except IntegrityError:
            # A second near-simultaneous request can pass the pre-check. Let the
            # database's unique constraint remain the final duplicate safeguard.
            db.rollback()
            existing = db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id == decision["student_id"],
                AttendanceRecord.session_id == req.session_id,
            ).first()
            decision.update({
                "decision": "DUPLICATE",
                "reason": "Attendance already marked for this session.",
                "attendance_id": existing.attendance_id if existing else None,
            })
            return AttendanceDecision(**decision)

        decision["attendance_id"] = record.attendance_id

        # Step 6: Create manual review entry if borderline
        if decision["decision"] == "MANUAL_REVIEW":
            review = ManualReview(
                attendance_id=record.attendance_id,
                student_id=decision["student_id"],
                session_id=req.session_id,
                recognition_confidence=decision["recognition_confidence"],
                liveness_status=decision["liveness_status"],
                liveness_score=decision["liveness_score"],
                status="PENDING",
            )
            db.add(review)
            db.commit()

    return AttendanceDecision(**decision)


def _get_session_subject_id(session_id: int, db: Session) -> int:
    """Get the subject_id for a given session."""
    session = db.query(AttendanceSession).filter(
        AttendanceSession.session_id == session_id
    ).first()
    return session.subject_id if session else 0


@router.get(
    "/records",
    response_model=list[AttendanceRecordResponse],
    summary="Get attendance records with optional filtering",
)
def get_attendance_records(
    session_id: int = None,
    student_id: int = None,
    subject_id: int = None,
    date: str = None,
    status: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get attendance records with optional filters."""
    query = db.query(AttendanceRecord)

    if session_id:
        query = query.filter(AttendanceRecord.session_id == session_id)
    if student_id:
        query = query.filter(AttendanceRecord.student_id == student_id)
    if subject_id:
        query = query.filter(AttendanceRecord.subject_id == subject_id)
    if date:
        query = query.filter(AttendanceRecord.date == date)
    if status:
        query = query.filter(AttendanceRecord.status == status)

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit).all()

    results = []
    for r in records:
        student = db.query(Student).filter(Student.student_id == r.student_id).first()
        subject = db.query(Subject).filter(Subject.subject_id == r.subject_id).first()

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


@router.get(
    "/student/{student_id}",
    response_model=list[AttendanceRecordResponse],
    summary="Get attendance records for a specific student",
)
def get_student_attendance(student_id: int, db: Session = Depends(get_db)):
    """Get all attendance records for a student."""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student_id
    ).order_by(AttendanceRecord.timestamp.desc()).all()

    results = []
    for r in records:
        subject = db.query(Subject).filter(Subject.subject_id == r.subject_id).first()
        results.append(AttendanceRecordResponse(
            attendance_id=r.attendance_id,
            student_id=r.student_id,
            student_code=student.student_code,
            student_name=student.name,
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
