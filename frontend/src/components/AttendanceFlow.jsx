/**
 * VeriAttend — Attendance Flow Component
 *
 * Multi-step attendance workflow:
 * 1. CAMERA_READY → Show camera, wait for face detection
 * 2. DETECTING_FACE → Face detection in progress
 * 3. VERIFYING_LIVENESS → Running liveness check
 * 4. RECOGNIZING → Identity recognition
 * 5. CHECKING_ATTENDANCE → Decision engine processing
 * 6. ATTENDANCE_SUCCESS → Marked present
 * 7. MANUAL_REVIEW → Sent to review queue
 * 8. REJECTED → Attendance denied
 * 9. ERROR → Something went wrong
 */

import { useState, useRef, useCallback } from 'react';
import Camera from './Camera';
import StatusDisplay from './StatusDisplay';
import { attendanceAPI, livenessAPI } from '../api/client';

const FLOW_STATES = {
  IDLE: 'IDLE',
  DETECTING_FACE: 'DETECTING_FACE',
  VERIFYING_LIVENESS: 'VERIFYING_LIVENESS',
  RECOGNIZING: 'RECOGNIZING',
  CHECKING_ATTENDANCE: 'CHECKING_ATTENDANCE',
  ATTENDANCE_SUCCESS: 'ATTENDANCE_SUCCESS',
  MANUAL_REVIEW: 'MANUAL_REVIEW',
  REJECTED: 'REJECTED',
  DUPLICATE: 'DUPLICATE',
  ERROR: 'ERROR',
};

const STATUS_CONFIG = {
  IDLE: { text: 'Position your face inside the frame', icon: '👤', type: 'idle' },
  DETECTING_FACE: { text: 'Detecting face...', icon: '🔍', type: 'processing' },
  VERIFYING_LIVENESS: { text: 'Verifying liveness...', icon: '✨', type: 'processing' },
  RECOGNIZING: { text: 'Recognizing face...', icon: '🧠', type: 'processing' },
  CHECKING_ATTENDANCE: { text: 'Processing attendance...', icon: '⏳', type: 'processing' },
  ATTENDANCE_SUCCESS: { text: 'Attendance marked successfully!', icon: '✅', type: 'success' },
  MANUAL_REVIEW: { text: 'Sent to manual review', icon: '📋', type: 'warning' },
  REJECTED: { text: 'Attendance rejected', icon: '❌', type: 'error' },
  DUPLICATE: { text: 'Already marked present', icon: '📌', type: 'warning' },
  ERROR: { text: 'An error occurred', icon: '⚠️', type: 'error' },
};

export default function AttendanceFlow({ sessionId, onComplete }) {
  const cameraRef = useRef(null);
  const [flowState, setFlowState] = useState(FLOW_STATES.IDLE);
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [cameraEnabled, setCameraEnabled] = useState(false);

  const processFrame = useCallback(async () => {
    if (isProcessing || !cameraRef.current || !sessionId) return;

    const frame = cameraRef.current.captureFrame();
    if (!frame) return;

    setIsProcessing(true);

    try {
      // Step 1: Detection + Liveness + Recognition + Decision (all in one backend call)
      setFlowState(FLOW_STATES.DETECTING_FACE);
      await new Promise((r) => setTimeout(r, 300)); // Brief visual feedback

      setFlowState(FLOW_STATES.VERIFYING_LIVENESS);
      await new Promise((r) => setTimeout(r, 300));

      setFlowState(FLOW_STATES.RECOGNIZING);
      await new Promise((r) => setTimeout(r, 300));

      setFlowState(FLOW_STATES.CHECKING_ATTENDANCE);

      const response = await attendanceAPI.mark({
        session_id: sessionId,
        frame_data: frame,
      });

      const decision = response.data;
      setResult(decision);

      switch (decision.decision) {
        case 'APPROVED':
          setFlowState(FLOW_STATES.ATTENDANCE_SUCCESS);
          break;
        case 'MANUAL_REVIEW':
          setFlowState(FLOW_STATES.MANUAL_REVIEW);
          break;
        case 'DUPLICATE':
          setFlowState(FLOW_STATES.DUPLICATE);
          break;
        case 'UNKNOWN':
        case 'REJECTED':
        default:
          setFlowState(FLOW_STATES.REJECTED);
          setErrorMessage(decision.reason);
          break;
      }

      if (onComplete) onComplete(decision);
    } catch (err) {
      setFlowState(FLOW_STATES.ERROR);
      setErrorMessage(err.response?.data?.detail || err.message || 'Unknown error');
    } finally {
      setIsProcessing(false);
      // Release the webcam as soon as this attempt is complete. The Camera
      // component unmounts and stops its MediaStream tracks.
      cameraRef.current?.stopCamera();
      setCameraEnabled(false);
    }
  }, [isProcessing, sessionId, onComplete]);

  const resetFlow = () => {
    setFlowState(FLOW_STATES.IDLE);
    setResult(null);
    setErrorMessage('');
  };

  const startAttendanceCamera = () => {
    setResult(null);
    setErrorMessage('');
    setFlowState(FLOW_STATES.IDLE);
    setCameraEnabled(true);
  };

  const stopAttendanceCamera = () => {
    // Stop tracks immediately, rather than waiting for React to unmount.
    cameraRef.current?.stopCamera();
    setCameraEnabled(false);
  };

  const statusConfig = STATUS_CONFIG[flowState] || STATUS_CONFIG.IDLE;
  const isTerminal = ['ATTENDANCE_SUCCESS', 'MANUAL_REVIEW', 'REJECTED', 'DUPLICATE', 'ERROR'].includes(flowState);

  const cameraStatusClass = flowState === 'ATTENDANCE_SUCCESS'
    ? 'camera-container--success'
    : ['REJECTED', 'ERROR'].includes(flowState)
      ? 'camera-container--error'
      : '';

  return (
    <div className="animate-in">
      {cameraEnabled ? (
        <Camera
          ref={cameraRef}
          statusClass={cameraStatusClass}
        />
      ) : (
        <div className="card text-center" style={{ padding: '2rem' }}>
          <div style={{ fontSize: '2.5rem' }}>📷</div>
          <h3 className="mt-1">Camera is off</h3>
          <p className="text-muted text-sm mt-1">Start it only when a student is ready to mark attendance.</p>
        </div>
      )}

      {/* Status Bar */}
      <div className="mt-2">
        <StatusDisplay
          icon={statusConfig.icon}
          text={statusConfig.text}
          type={statusConfig.type}
          subtext={errorMessage && flowState === 'ERROR' ? errorMessage : undefined}
        />
      </div>

      {/* Result Details */}
      {result && isTerminal && (
        <div className="attendance-result mt-2">
          <div className="attendance-result__details">
            {result.student_name && (
              <div className="attendance-result__detail">
                <div className="attendance-result__detail-label">Student</div>
                <div className="attendance-result__detail-value">{result.student_name}</div>
              </div>
            )}
            {result.recognition_confidence > 0 && (
              <div className="attendance-result__detail">
                <div className="attendance-result__detail-label">Confidence</div>
                <div className="attendance-result__detail-value">
                  {(result.recognition_confidence * 100).toFixed(0)}%
                </div>
              </div>
            )}
            <div className="attendance-result__detail">
              <div className="attendance-result__detail-label">Liveness</div>
              <div className="attendance-result__detail-value">
                {result.liveness_status === 'PASS' ? '✅ Verified' :
                  result.liveness_status === 'FAIL' ? '❌ Failed' : '⚠️ ' + result.liveness_status}
              </div>
            </div>
            <div className="attendance-result__detail">
              <div className="attendance-result__detail-label">Time</div>
              <div className="attendance-result__detail-value">
                {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>

          {result.reason && (
            <p className="text-sm text-muted mt-2">{result.reason}</p>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2 mt-3" style={{ justifyContent: 'center' }}>
        {!cameraEnabled && flowState === FLOW_STATES.IDLE && (
          <button
            className="btn btn--primary btn--lg"
            onClick={startAttendanceCamera}
            disabled={!sessionId}
            id="btn-start-attendance-camera"
          >
            📷 Start Camera to Mark Attendance
          </button>
        )}

        {cameraEnabled && flowState === FLOW_STATES.IDLE && (
          <button
            className="btn btn--primary btn--lg"
            onClick={processFrame}
            disabled={!sessionId}
            id="btn-capture-attendance"
          >
            📸 Capture & Verify
          </button>
        )}

        {cameraEnabled && !isProcessing && flowState === FLOW_STATES.IDLE && (
          <button className="btn btn--secondary" onClick={stopAttendanceCamera}>
            Turn Camera Off
          </button>
        )}

        {isTerminal && (
          <button className="btn btn--secondary" onClick={resetFlow} id="btn-try-again">
            🔄 Try Again
          </button>
        )}
      </div>
    </div>
  );
}
