/**
 * VeriAttend — Review Card Component
 *
 * Displays a borderline-confidence attendance case for admin review.
 */

import { useState } from 'react';
import { reviewsAPI } from '../api/client';

export default function ReviewCard({ review, onDecision }) {
  const [loading, setLoading] = useState(false);
  const [notes, setNotes] = useState('');

  const handleDecision = async (decision) => {
    setLoading(true);
    try {
      await reviewsAPI.decide(review.review_id, decision, notes);
      if (onDecision) onDecision(review.review_id, decision);
    } catch (err) {
      console.error('Review decision failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const confidencePercent = (review.recognition_confidence * 100).toFixed(0);
  const confidenceColor = review.recognition_confidence >= 0.7 ? 'high' :
    review.recognition_confidence >= 0.5 ? 'medium' : 'low';

  return (
    <div className="card animate-in">
      <div className="flex justify-between items-center mb-2">
        <div>
          <h4>{review.student_name || `Student #${review.student_id}`}</h4>
          {review.student_code && (
            <span className="text-sm text-muted">{review.student_code}</span>
          )}
        </div>
        <span className={`badge badge--${review.status === 'PENDING' ? 'warning' : review.status === 'APPROVED' ? 'success' : 'error'}`}>
          {review.status}
        </span>
      </div>

      {/* Confidence */}
      <div className="mb-2">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-muted">Recognition Confidence</span>
          <span style={{ fontWeight: 600 }}>{confidencePercent}%</span>
        </div>
        <div className="confidence-bar">
          <div
            className={`confidence-bar__fill confidence-bar__fill--${confidenceColor}`}
            style={{ width: `${confidencePercent}%` }}
          />
        </div>
      </div>

      {/* Liveness */}
      <div className="flex gap-2 mb-2" style={{ flexWrap: 'wrap' }}>
        <span className={`badge ${review.liveness_status === 'PASS' ? 'badge--success' : 'badge--warning'}`}>
          Liveness: {review.liveness_status}
        </span>
        {review.created_at && (
          <span className="badge badge--neutral">
            {new Date(review.created_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Actions (only for pending reviews) */}
      {review.status === 'PENDING' && (
        <>
          <div className="input-group mb-2">
            <label className="input-group__label">Review Notes (optional)</label>
            <input
              className="input"
              type="text"
              placeholder="Add notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <div className="flex gap-1">
            <button
              className="btn btn--success btn--sm"
              onClick={() => handleDecision('APPROVED')}
              disabled={loading}
              style={{ flex: 1 }}
            >
              ✅ Approve
            </button>
            <button
              className="btn btn--danger btn--sm"
              onClick={() => handleDecision('REJECTED')}
              disabled={loading}
              style={{ flex: 1 }}
            >
              ❌ Reject
            </button>
          </div>
        </>
      )}
    </div>
  );
}
