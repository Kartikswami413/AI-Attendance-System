"""
VeriAttend — Recognition Routes

POST /api/recognition/detect     — Detect faces in a frame
POST /api/recognition/recognize  — Detect + recognize face identity
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np
import base64
import cv2

from models.database import get_db
from models.schemas import FaceDetectionResult, RecognitionResult, BoundingBox
from services.face_detection import detect_faces, get_face_landmarks, compute_face_embedding
from services.face_recognition_service import recognize_face

router = APIRouter(prefix="/api/recognition", tags=["Recognition"])


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


class FrameInput:
    """Simple model for frame-only endpoints."""
    pass


@router.post(
    "/detect",
    response_model=FaceDetectionResult,
    summary="Detect faces in a camera frame",
    description=(
        "Detects faces in the provided base64-encoded image. "
        "Returns status (NO_FACE, ONE_FACE, MULTIPLE_FACES, LOW_QUALITY) "
        "and bounding box coordinates for each detected face."
    ),
)
def detect_faces_endpoint(body: dict, db: Session = Depends(get_db)):
    """
    Detect faces in a frame without performing identity recognition.
    Useful for real-time face tracking UI feedback.
    """
    frame_data = body.get("frame_data")
    if not frame_data:
        raise HTTPException(status_code=400, detail="frame_data is required.")

    try:
        image_np = _decode_frame(frame_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data.")

    result = detect_faces(image_np)

    return FaceDetectionResult(
        status=result["status"],
        num_faces=result["num_faces"],
        bounding_boxes=[
            BoundingBox(**bb) for bb in result["bounding_boxes"]
        ],
        message=result["message"],
    )


@router.post(
    "/recognize",
    response_model=RecognitionResult,
    summary="Detect and recognize a face",
    description=(
        "Full recognition pipeline: detects a face, extracts the 128D embedding, "
        "compares against registered students, and returns the best match with "
        "confidence score. Rejects frames with zero or multiple faces."
    ),
)
def recognize_face_endpoint(body: dict, db: Session = Depends(get_db)):
    """
    Detect + recognize: identifies whose face is in the frame.

    Pipeline:
        1. Decode base64 image
        2. Detect faces (reject if != 1)
        3. Extract landmarks
        4. Compute 128D embedding
        5. Compare against registered embeddings
        6. Return recognition result with confidence
    """
    frame_data = body.get("frame_data")
    if not frame_data:
        raise HTTPException(status_code=400, detail="frame_data is required.")

    try:
        image_np = _decode_frame(frame_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data.")

    # Step 1: Detect faces
    detection = detect_faces(image_np)

    if detection["status"] != "ONE_FACE":
        return RecognitionResult(
            recognized=False,
            confidence=0.0,
            distance=float("inf"),
            message=detection["message"],
        )

    # Step 2: Get embedding
    face_rect = detection["faces"][0]
    landmarks = get_face_landmarks(image_np, face_rect)
    embedding = compute_face_embedding(image_np, landmarks)

    # Step 3: Recognize
    result = recognize_face(embedding, db)

    return RecognitionResult(
        recognized=result["recognized"],
        student_id=result["student_id"],
        student_code=result["student_code"],
        name=result["name"],
        confidence=result["confidence"],
        distance=result["distance"],
        message=result["message"],
    )
