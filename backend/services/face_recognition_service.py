"""
VeriAttend — Face Recognition Service

Identity recognition pipeline: compares a face embedding against
registered student embeddings to find the best match.

Uses Euclidean distance as the similarity metric.
Preserves the SVM classifier approach from existing SnapClass with
added confidence scoring and UNKNOWN handling.

Similarity metric:
    Euclidean distance between 128D face embeddings (dlib ResNet).
    - Same person: typically distance < 0.6
    - Different person: typically distance > 0.6
    - Confidence = max(0, 1.0 - distance / threshold)
"""

import numpy as np
from sklearn.svm import SVC
from sqlalchemy.orm import Session
import logging

from config import settings
from models.database import Student

logger = logging.getLogger(__name__)

# ── Classifier Cache ──
_classifier_cache = None


def _build_classifier(db: Session) -> dict | None:
    """
    Build an SVM classifier from all registered student embeddings.

    This trains a linear SVM on the stored face embeddings so that
    recognition can use both SVM prediction and distance verification.

    Returns:
        dict with 'clf', 'embeddings', 'student_ids', 'student_map' or None if < 1 student.
    """
    global _classifier_cache

    students = db.query(Student).filter(
        Student.face_embedding.isnot(None), Student.is_active.is_(True)
    ).all()

    if not students:
        logger.warning("No students with face embeddings found.")
        return None

    X = []
    y = []
    student_map = {}

    for student in students:
        embedding = student.face_embedding
        if embedding and len(embedding) == 128:
            X.append(np.array(embedding, dtype=np.float64))
            y.append(student.student_id)
            student_map[student.student_id] = {
                "student_code": student.student_code,
                "name": student.name,
            }

    if len(X) == 0:
        return None

    clf = None
    if len(set(y)) >= 2:
        # Need at least 2 classes for SVM
        clf = SVC(kernel="linear", probability=True, class_weight="balanced")
        try:
            clf.fit(X, y)
        except ValueError as e:
            logger.error(f"SVM training failed: {e}")
            clf = None

    _classifier_cache = {
        "clf": clf,
        "embeddings": X,
        "student_ids": y,
        "student_map": student_map,
    }

    logger.info(f"Classifier built with {len(X)} student(s).")
    return _classifier_cache


def invalidate_classifier_cache():
    """Clear the cached classifier so it will be rebuilt on next recognition."""
    global _classifier_cache
    _classifier_cache = None
    logger.info("Classifier cache invalidated.")


def recognize_face(face_embedding: np.ndarray, db: Session) -> dict:
    """
    Recognize a face by comparing its embedding against registered students.

    Pipeline:
        1. If SVM classifier exists (≥2 students), use it to predict candidate
        2. If only 1 student registered, compare directly
        3. Compute Euclidean distance to the candidate's stored embedding
        4. Calculate confidence score
        5. Return structured result

    Args:
        face_embedding: 128D numpy array from face detection service
        db: database session

    Returns:
        dict with keys:
            - recognized: bool
            - student_id: int or None
            - student_code: str or None
            - name: str or None
            - confidence: float (0.0 - 1.0)
            - distance: float (raw Euclidean distance)
            - message: str
    """
    global _classifier_cache

    # Build or use cached classifier
    model_data = _classifier_cache
    if model_data is None:
        model_data = _build_classifier(db)

    if model_data is None:
        return {
            "recognized": False,
            "student_id": None,
            "student_code": None,
            "name": None,
            "confidence": 0.0,
            "distance": float("inf"),
            "message": "No registered students found.",
        }

    clf = model_data["clf"]
    stored_embeddings = model_data["embeddings"]
    stored_ids = model_data["student_ids"]
    student_map = model_data["student_map"]
    threshold = settings.RECOGNITION_THRESHOLD

    # Step 1: Find the best candidate
    if clf is not None:
        # SVM prediction for initial candidate selection
        predicted_id = int(clf.predict([face_embedding])[0])
    else:
        # Only 1 student — compare directly
        predicted_id = stored_ids[0]

    # Step 2: Compute Euclidean distance to the predicted student's embedding
    candidate_idx = stored_ids.index(predicted_id)
    candidate_embedding = stored_embeddings[candidate_idx]
    distance = float(np.linalg.norm(candidate_embedding - face_embedding))

    # Step 3: Also find the absolute nearest neighbor (in case SVM is wrong)
    distances = [
        float(np.linalg.norm(emb - face_embedding)) for emb in stored_embeddings
    ]
    nearest_idx = int(np.argmin(distances))
    nearest_distance = distances[nearest_idx]
    nearest_id = stored_ids[nearest_idx]

    # Use the nearest neighbor if it's actually closer
    if nearest_distance < distance:
        predicted_id = nearest_id
        distance = nearest_distance

    # Step 4: Calculate confidence
    # Confidence = 1.0 - (distance / threshold), clamped to [0, 1]
    confidence = max(0.0, min(1.0, 1.0 - (distance / threshold)))

    # Step 5: Determine if recognized
    if distance <= threshold:
        student_info = student_map.get(predicted_id, {})
        return {
            "recognized": True,
            "student_id": predicted_id,
            "student_code": student_info.get("student_code"),
            "name": student_info.get("name"),
            "confidence": round(confidence, 4),
            "distance": round(distance, 4),
            "message": f"Recognized as {student_info.get('name', 'Unknown')} with {confidence:.0%} confidence.",
        }
    else:
        return {
            "recognized": False,
            "student_id": None,
            "student_code": None,
            "name": None,
            "confidence": round(confidence, 4),
            "distance": round(distance, 4),
            "message": "Face not recognized. No match above the confidence threshold.",
        }
