/**
 * VeriAttend — WebRTC Camera Component
 *
 * Handles:
 * - Camera permission request
 * - Live video preview (mirrored)
 * - Frame capture as base64
 * - Permission denied / unavailable camera states
 * - Face guide overlay
 */

import { useRef, useState, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';

const CAMERA_STATES = {
  INITIALIZING: 'INITIALIZING',
  READY: 'READY',
  DENIED: 'DENIED',
  UNAVAILABLE: 'UNAVAILABLE',
  ERROR: 'ERROR',
};

const Camera = forwardRef(function Camera({ onFrame, autoCapture = false, captureInterval = 1500, statusClass = '' }, ref) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);
  const [cameraState, setCameraState] = useState(CAMERA_STATES.INITIALIZING);
  const [error, setError] = useState('');

  // Start camera
  const startCamera = useCallback(async () => {
    setCameraState(CAMERA_STATES.INITIALIZING);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setCameraState(CAMERA_STATES.READY);
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCameraState(CAMERA_STATES.DENIED);
        setError('Camera permission denied. Please allow camera access in your browser settings.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setCameraState(CAMERA_STATES.UNAVAILABLE);
        setError('No camera found. Please connect a camera.');
      } else {
        setCameraState(CAMERA_STATES.ERROR);
        setError(`Camera error: ${err.message}`);
      }
    }
  }, []);

  // Stop camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Capture a single frame as base64
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || videoRef.current.readyState < 2 ||
        !videoRef.current.videoWidth || !videoRef.current.videoHeight) return null;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
  }, []);

  // Expose methods to parent
  useImperativeHandle(ref, () => ({
    captureFrame,
    startCamera,
    stopCamera,
    getState: () => cameraState,
  }));

  // The video node mounts after READY is set. Attach the acquired stream here,
  // after that render, so it cannot be lost on an initially null video ref.
  useEffect(() => {
    const video = videoRef.current;
    if (cameraState !== CAMERA_STATES.READY || !video || !streamRef.current) return;
    // Do not reload the same stream; Chrome aborts a pending play() when a
    // duplicate srcObject assignment occurs during a development-mode refresh.
    if (video.srcObject !== streamRef.current) {
      video.srcObject = streamRef.current;
    }
    video.play().catch((err) => {
      // A second mount/reload can abort the first play request. The final
      // stream remains valid and autoplay will start it, so this is not a
      // camera failure to show to the user.
      if (err.name === 'AbortError' || err.message.includes('interrupted by a new load request')) return;
      setCameraState(CAMERA_STATES.ERROR);
      setError(`Camera preview could not start: ${err.message}`);
    });
  }, [cameraState]);

  // Auto-capture at intervals
  useEffect(() => {
    if (autoCapture && cameraState === CAMERA_STATES.READY && onFrame) {
      intervalRef.current = setInterval(() => {
        const frame = captureFrame();
        if (frame) onFrame(frame);
      }, captureInterval);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [autoCapture, cameraState, captureInterval, captureFrame, onFrame]);

  // Start on mount, stop on unmount
  useEffect(() => {
    startCamera();
    return stopCamera;
  }, [startCamera, stopCamera]);

  const containerClass = `camera-container ${statusClass} ${
    cameraState === CAMERA_STATES.READY ? 'camera-container--active' : ''
  }`;

  return (
    <div className={containerClass}>
      {/* Hidden canvas for frame capture */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {cameraState === CAMERA_STATES.READY && (
        <>
          <video
            ref={videoRef}
            className="camera-video"
            autoPlay
            playsInline
            muted
          />
          <div className="camera-overlay">
            <div className="camera-face-guide" />
          </div>
        </>
      )}

      {cameraState === CAMERA_STATES.INITIALIZING && (
        <div className="spinner-container">
          <div className="spinner" />
          <span>Starting camera...</span>
        </div>
      )}

      {cameraState === CAMERA_STATES.DENIED && (
        <div className="empty-state">
          <div className="empty-state__icon">🚫</div>
          <div className="empty-state__title">Camera Access Denied</div>
          <div className="empty-state__text">{error}</div>
          <button className="btn btn--primary mt-2" onClick={startCamera}>
            Try Again
          </button>
        </div>
      )}

      {cameraState === CAMERA_STATES.UNAVAILABLE && (
        <div className="empty-state">
          <div className="empty-state__icon">📷</div>
          <div className="empty-state__title">No Camera Found</div>
          <div className="empty-state__text">{error}</div>
        </div>
      )}

      {cameraState === CAMERA_STATES.ERROR && (
        <div className="empty-state">
          <div className="empty-state__icon">⚠️</div>
          <div className="empty-state__title">Camera Error</div>
          <div className="empty-state__text">{error}</div>
          <button className="btn btn--secondary mt-2" onClick={startCamera}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
});

export default Camera;
