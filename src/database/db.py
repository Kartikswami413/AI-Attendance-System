"""
Database access layer — SQLAlchemy queries against local SQLite.

Every function returns plain dicts (or lists of dicts) matching the
format previously returned by the Supabase client, so downstream
Streamlit screens/components don't need any changes.
"""

import bcrypt
from sqlalchemy import func
from src.database.config import get_session

# Import backend models (backend/ is already on sys.path via config.py)
from models.database import (
    Teacher, Student, Subject, SubjectStudent,
    AttendanceRecord, AttendanceSession,
)


# ─── Helpers ────────────────────────────────────────────────────────

def _teacher_to_dict(t):
    return {
        "teacher_id": t.teacher_id,
        "username": t.username,
        "name": t.name,
        "password": t.password_hash,      # kept as 'password' for check_pass compat
        "created_at": str(t.created_at) if t.created_at else None,
    }


def _student_to_dict(s):
    return {
        "student_id": s.student_id,
        "student_code": s.student_code,
        "name": s.name,
        "email": s.email,
        "department": s.department,
        "year": s.year,
        "face_embedding": s.face_embedding,
        "voice_embedding": s.voice_embedding,
        "created_at": str(s.created_at) if s.created_at else None,
    }


def _subject_to_dict(s):
    return {
        "subject_id": s.subject_id,
        "subject_code": s.subject_code,
        "name": s.name,
        "section": s.section,
        "teacher_id": s.teacher_id,
        "created_at": str(s.created_at) if s.created_at else None,
    }


# ─── Password Utilities ────────────────────────────────────────────

def hash_pass(pwd):
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


def check_pass(pwd, hashed):
    return bcrypt.checkpw(pwd.encode(), hashed.encode())


# ─── Teacher Functions ──────────────────────────────────────────────

def check_teacher_exists(username):
    """Return True if username is already taken."""
    session = get_session()
    try:
        count = session.query(Teacher).filter(Teacher.username == username).count()
        return count > 0
    finally:
        session.close()


def create_teacher(username, password, name):
    session = get_session()
    try:
        teacher = Teacher(
            username=username,
            password_hash=hash_pass(password),
            name=name,
        )
        session.add(teacher)
        session.commit()
        session.refresh(teacher)
        return [_teacher_to_dict(teacher)]
    finally:
        session.close()


def teacher_login(username, password):
    session = get_session()
    try:
        teacher = session.query(Teacher).filter(Teacher.username == username).first()
        if teacher and check_pass(password, teacher.password_hash):
            return _teacher_to_dict(teacher)
        return None
    finally:
        session.close()


# ─── Student Functions ──────────────────────────────────────────────

def get_all_students():
    session = get_session()
    try:
        students = session.query(Student).all()
        return [_student_to_dict(s) for s in students]
    finally:
        session.close()


def create_student(new_name, face_embedding=None, voice_embedding=None):
    session = get_session()
    try:
        # Auto-generate a student_code
        max_id = session.query(func.max(Student.student_id)).scalar() or 0
        student_code = f"STU{max_id + 1:04d}"

        student = Student(
            student_code=student_code,
            name=new_name,
            face_embedding=face_embedding,
            voice_embedding=voice_embedding,
        )
        session.add(student)
        session.commit()
        session.refresh(student)
        return [_student_to_dict(student)]
    finally:
        session.close()


# ─── Subject Functions ──────────────────────────────────────────────

def create_subject(subject_code, name, section, teacher_id):
    session = get_session()
    try:
        subject = Subject(
            subject_code=subject_code,
            name=name,
            section=section,
            teacher_id=teacher_id,
        )
        session.add(subject)
        session.commit()
        session.refresh(subject)
        return [_subject_to_dict(subject)]
    finally:
        session.close()


def get_teacher_subjects(teacher_id):
    """Get all subjects for a teacher with enrollment counts and session counts."""
    session = get_session()
    try:
        subjects = session.query(Subject).filter(Subject.teacher_id == teacher_id).all()
        result = []
        for sub in subjects:
            total_students = (
                session.query(func.count(SubjectStudent.id))
                .filter(SubjectStudent.subject_id == sub.subject_id)
                .scalar()
            )
            total_classes = (
                session.query(func.count(AttendanceSession.session_id))
                .filter(AttendanceSession.subject_id == sub.subject_id)
                .scalar()
            )
            d = _subject_to_dict(sub)
            d["total_students"] = total_students or 0
            d["total_classes"] = total_classes or 0
            result.append(d)
        return result
    finally:
        session.close()


def get_subject_by_code(code):
    """Look up a subject by its subject_code. Returns dict or None."""
    session = get_session()
    try:
        sub = session.query(Subject).filter(Subject.subject_code == code).first()
        if sub:
            return _subject_to_dict(sub)
        return None
    finally:
        session.close()


# ─── Enrollment Functions ───────────────────────────────────────────

def enroll_student_to_subject(student_id, subject_id):
    session = get_session()
    try:
        enrollment = SubjectStudent(
            student_id=student_id,
            subject_id=subject_id,
        )
        session.add(enrollment)
        session.commit()
        session.refresh(enrollment)
        return [{"student_id": student_id, "subject_id": subject_id}]
    finally:
        session.close()


def unenroll_student_to_subject(student_id, subject_id):
    session = get_session()
    try:
        enrollment = (
            session.query(SubjectStudent)
            .filter(
                SubjectStudent.student_id == student_id,
                SubjectStudent.subject_id == subject_id,
            )
            .first()
        )
        if enrollment:
            session.delete(enrollment)
            session.commit()
        return []
    finally:
        session.close()


def check_enrollment(student_id, subject_id):
    """Return True if student is already enrolled in the subject."""
    session = get_session()
    try:
        count = (
            session.query(SubjectStudent)
            .filter(
                SubjectStudent.student_id == student_id,
                SubjectStudent.subject_id == subject_id,
            )
            .count()
        )
        return count > 0
    finally:
        session.close()


def get_enrolled_students(subject_id):
    """
    Get all students enrolled in a subject.
    Returns list of dicts matching old Supabase format:
    [{"students": {student_dict}, "subject_id": ...}, ...]
    """
    session = get_session()
    try:
        enrollments = (
            session.query(SubjectStudent)
            .filter(SubjectStudent.subject_id == subject_id)
            .all()
        )
        result = []
        for e in enrollments:
            student = session.query(Student).filter(Student.student_id == e.student_id).first()
            if student:
                result.append({
                    "student_id": e.student_id,
                    "subject_id": e.subject_id,
                    "students": _student_to_dict(student),
                })
        return result
    finally:
        session.close()


def get_student_subjects(student_id):
    """
    Get all subjects a student is enrolled in.
    Returns list of dicts: [{"subjects": {subject_dict}, ...}, ...]
    """
    session = get_session()
    try:
        enrollments = (
            session.query(SubjectStudent)
            .filter(SubjectStudent.student_id == student_id)
            .all()
        )
        result = []
        for e in enrollments:
            subject = session.query(Subject).filter(Subject.subject_id == e.subject_id).first()
            if subject:
                result.append({
                    "student_id": e.student_id,
                    "subject_id": e.subject_id,
                    "subjects": _subject_to_dict(subject),
                })
        return result
    finally:
        session.close()


# ─── Attendance Functions ───────────────────────────────────────────

def get_student_attendance(student_id):
    """
    Get attendance records for a student.
    Returns list of dicts with nested 'subjects' key for compatibility.
    """
    session = get_session()
    try:
        records = (
            session.query(AttendanceRecord)
            .filter(AttendanceRecord.student_id == student_id)
            .all()
        )
        result = []
        for r in records:
            subject = session.query(Subject).filter(Subject.subject_id == r.subject_id).first()
            result.append({
                "student_id": r.student_id,
                "subject_id": r.subject_id,
                "timestamp": str(r.timestamp) if r.timestamp else None,
                "is_present": r.status == "PRESENT",
                "subjects": _subject_to_dict(subject) if subject else {},
            })
        return result
    finally:
        session.close()


def create_attendance(logs):
    """
    Insert attendance records from a list of log dicts.
    Each log: {"student_id": int, "subject_id": int, "timestamp": str, "is_present": bool}
    """
    session = get_session()
    try:
        for log in logs:
            record = AttendanceRecord(
                student_id=log["student_id"],
                subject_id=log["subject_id"],
                date=log["timestamp"][:10] if log.get("timestamp") else "",
                status="PRESENT" if log.get("is_present") else "ABSENT",
                verification_method="AUTO_HIGH_CONFIDENCE",
            )
            session.add(record)
        session.commit()
        return logs
    finally:
        session.close()


def get_attendance_for_teacher(teacher_id):
    """
    Get all attendance records for subjects owned by a teacher.
    Returns list of dicts with nested 'subjects' key.
    """
    session = get_session()
    try:
        # Get all subject IDs for this teacher
        subject_ids = [
            s.subject_id
            for s in session.query(Subject).filter(Subject.teacher_id == teacher_id).all()
        ]
        if not subject_ids:
            return []

        records = (
            session.query(AttendanceRecord)
            .filter(AttendanceRecord.subject_id.in_(subject_ids))
            .all()
        )

        # Cache subjects
        subjects_cache = {}
        for sid in subject_ids:
            sub = session.query(Subject).filter(Subject.subject_id == sid).first()
            if sub:
                subjects_cache[sid] = _subject_to_dict(sub)

        result = []
        for r in records:
            result.append({
                "student_id": r.student_id,
                "subject_id": r.subject_id,
                "timestamp": str(r.timestamp) if r.timestamp else None,
                "is_present": r.status == "PRESENT",
                "subjects": subjects_cache.get(r.subject_id, {}),
            })
        return result
    finally:
        session.close()
