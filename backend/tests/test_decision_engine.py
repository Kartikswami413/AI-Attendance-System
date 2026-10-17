"""
VeriAttend — Decision Engine Tests

Tests the attendance decision engine with all 15 required scenarios:
1. Student registration ✓ (via API test)
2. Duplicate student registration ✓
3. Face detection with no face ✓
4. Multiple face detection ✓
5. Successful recognition ✓
6. Unknown face ✓
7. Liveness pass ✓
8. Liveness failure ✓
9. High-confidence attendance ✓
10. Borderline-confidence manual review ✓
11. Low-confidence rejection ✓
12. Duplicate attendance prevention ✓
13. Manual review approval ✓ (via API test)
14. Manual review rejection ✓ (via API test)
15. Invalid API requests ✓ (via API test)
"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch
from services.attendance_decision import AttendanceDecisionInput, make_attendance_decision


class MockDB:
    """Mock database session for testing."""
    def query(self, *args, **kwargs):
        return MockQuery()


class MockQuery:
    def filter(self, *args, **kwargs):
        return self
    def first(self):
        return None


def _make_input(
    detection_status="ONE_FACE",
    face_count=1,
    liveness_status="PASS",
    liveness_score=0.9,
    recognized=True,
    student_id=1,
    confidence=0.95,
    session_id=None,
):
    """Helper to create test inputs."""
    recognition_result = {
        "recognized": recognized,
        "student_id": student_id if recognized else None,
        "student_code": "CS001" if recognized else None,
        "name": "Test Student" if recognized else None,
        "confidence": confidence,
        "distance": 0.3 if recognized else 0.8,
        "message": "Recognized" if recognized else "Not recognized",
    }

    return AttendanceDecisionInput(
        face_detection_status=detection_status,
        face_count=face_count,
        liveness_status=liveness_status,
        liveness_score=liveness_score,
        recognition_result=recognition_result,
        session_id=session_id,
        db=MockDB(),
    )


# ── Test 3: No Face Detection ──
def test_no_face_detected():
    """Decision should REJECT when no face is detected."""
    inp = _make_input(detection_status="NO_FACE", face_count=0)
    result = make_attendance_decision(inp)
    assert result["decision"] == "REJECTED"
    assert "No face" in result["reason"]


# ── Test 4: Multiple Faces ──
def test_multiple_faces_detected():
    """Decision should REJECT when multiple faces are detected."""
    inp = _make_input(detection_status="MULTIPLE_FACES", face_count=3)
    result = make_attendance_decision(inp)
    assert result["decision"] == "REJECTED"
    assert "Multiple" in result["reason"]


# ── Test: Low Quality Image ──
def test_low_quality_image():
    """Decision should REJECT when image quality is too low."""
    inp = _make_input(detection_status="LOW_QUALITY")
    result = make_attendance_decision(inp)
    assert result["decision"] == "REJECTED"
    assert "quality" in result["reason"].lower()


# ── Test 8: Liveness Failure ──
def test_liveness_failure():
    """Decision should REJECT when liveness check fails."""
    inp = _make_input(liveness_status="FAIL", liveness_score=0.2)
    result = make_attendance_decision(inp)
    assert result["decision"] == "REJECTED"
    assert "Liveness" in result["reason"] or "liveness" in result["reason"].lower()


# ── Test 7: Liveness Pass (should proceed to recognition check) ──
def test_liveness_pass_with_high_confidence():
    """Decision should APPROVE when liveness passes and confidence is high."""
    inp = _make_input(liveness_status="PASS", confidence=0.95)
    result = make_attendance_decision(inp)
    assert result["decision"] == "APPROVED"
    assert result["liveness_status"] == "PASS"


# ── Test 6: Unknown Face ──
def test_unknown_face():
    """Decision should return UNKNOWN when face is not recognized."""
    inp = _make_input(recognized=False, confidence=0.1)
    result = make_attendance_decision(inp)
    assert result["decision"] == "UNKNOWN"
    assert result["student_id"] is None


# ── Test 5: Successful Recognition ──
def test_successful_recognition():
    """Decision should APPROVE with high confidence recognition."""
    inp = _make_input(recognized=True, confidence=0.92, student_id=42)
    result = make_attendance_decision(inp)
    assert result["decision"] == "APPROVED"
    assert result["student_id"] == 42
    assert result["recognition_confidence"] == 0.92


# ── Test 9: High Confidence Attendance ──
def test_high_confidence_auto_approved():
    """Confidence >= 0.75 should be auto-approved."""
    inp = _make_input(confidence=0.75)
    result = make_attendance_decision(inp)
    assert result["decision"] == "APPROVED"
    assert "auto-approved" in result["reason"].lower() or "auto" in result["reason"].lower()


# ── Test 10: Borderline Confidence ──
def test_borderline_confidence_manual_review():
    """Confidence between 0.55 and 0.75 should go to manual review."""
    inp = _make_input(confidence=0.65)
    result = make_attendance_decision(inp)
    assert result["decision"] == "MANUAL_REVIEW"
    assert "review" in result["reason"].lower()


# ── Test 11: Low Confidence Rejection ──
def test_low_confidence_rejected():
    """Confidence below 0.55 should be rejected."""
    inp = _make_input(confidence=0.40)
    result = make_attendance_decision(inp)
    assert result["decision"] == "REJECTED"
    assert "Low confidence" in result["reason"] or "low" in result["reason"].lower()


# ── Test 12: Duplicate Attendance ──
def test_duplicate_attendance():
    """Should return DUPLICATE when student already marked in session."""
    from datetime import datetime, timedelta
    from models.database import AttendanceSession, AttendanceRecord, SubjectStudent

    mock_session = MagicMock()
    mock_session.session_id = 1
    mock_session.subject_id = 1
    mock_session.is_active = True
    # Deliberately broad window so this unit test is independent of the host clock.
    mock_session.start_time = datetime(2000, 1, 1)
    mock_session.end_time = datetime(2100, 1, 1)

    mock_record = MagicMock()
    mock_record.attendance_id = 99

    class MockDBDuplicate:
        """Returns session for AttendanceSession query, record for AttendanceRecord query."""
        def query(self, model, *args, **kwargs):
            if model is AttendanceSession:
                return self._SessionQuery()
            if model is SubjectStudent:
                return self._EnrollmentQuery()
            return self._RecordQuery()

        class _SessionQuery:
            def filter(self, *a, **kw):
                return self
            def first(self_inner):
                return mock_session

        class _EnrollmentQuery:
            def filter(self, *a, **kw):
                return self
            def first(self_inner):
                return MagicMock()

        class _RecordQuery:
            def filter(self, *a, **kw):
                return self
            def first(self_inner):
                return mock_record

    inp = _make_input(confidence=0.95, session_id=1)
    inp.db = MockDBDuplicate()

    result = make_attendance_decision(inp)
    assert result["decision"] == "DUPLICATE"
    assert result["attendance_id"] == 99


# ── Test: Session not found ──
def test_inactive_session():
    """Should REJECT when session is not found."""

    class MockDBWithSession:
        def query(self, *args, **kwargs):
            return MockQueryNoSession()

    class MockQueryNoSession:
        def filter(self, *args, **kwargs):
            return self
        def first(self):
            return None  # Session not found

    inp = _make_input(confidence=0.95, session_id=999)
    inp.db = MockDBWithSession()

    result = make_attendance_decision(inp)
    assert result["decision"] == "REJECTED"
    assert "session" in result["reason"].lower()


# ── Test: Decision preserves student info ──
def test_decision_preserves_student_info():
    """Decision should include student details when recognized."""
    inp = _make_input(recognized=True, student_id=7, confidence=0.90)
    result = make_attendance_decision(inp)
    assert result["student_id"] == 7
    assert result["student_code"] == "CS001"
    assert result["student_name"] == "Test Student"


# ── Test: Decision reports liveness status ──
def test_decision_reports_liveness():
    """Decision should pass through liveness status and score."""
    inp = _make_input(liveness_status="PASS", liveness_score=0.88, confidence=0.90)
    result = make_attendance_decision(inp)
    assert result["liveness_status"] == "PASS"
    assert result["liveness_score"] == 0.88


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
