/**
 * VeriAttend — Review Queue Page
 *
 * Admin interface for reviewing borderline-confidence attendance cases.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ReviewCard from '../components/ReviewCard';
import { reviewsAPI } from '../api/client';

export default function ReviewQueue() {
  const navigate = useNavigate();
  const [reviews, setReviews] = useState([]);
  const [filter, setFilter] = useState('PENDING');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('veriattend_teacher');
    if (!stored) { navigate('/login'); return; }
    loadReviews();
  }, [filter, navigate]);

  const loadReviews = async () => {
    setLoading(true);
    try {
      const res = await reviewsAPI.list(filter || undefined);
      setReviews(res.data);
    } catch (err) {
      console.error('Load reviews error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = (reviewId, decision) => {
    setReviews((prev) =>
      prev.map((r) =>
        r.review_id === reviewId ? { ...r, status: decision.toUpperCase() } : r
      )
    );
  };

  const pendingCount = reviews.filter((r) => r.status === 'PENDING').length;

  return (
    <div className="app-layout">
      <header className="app-header">
        <a href="/dashboard" className="app-header__brand">
          <img src="https://i.ibb.co/YTYGn5qV/logo.png" alt="" className="app-header__logo" />
          <span className="app-header__title">VeriAttend</span>
        </a>
        <nav className="app-header__nav">
          <a href="/dashboard" className="btn btn--ghost btn--sm">← Dashboard</a>
        </nav>
      </header>

      <main className="app-main" style={{ maxWidth: 800, margin: '0 auto' }}>
        <div className="page-header animate-in">
          <div>
            <h1>📋 Manual Review Queue</h1>
            <p className="page-header__subtitle">
              {pendingCount} pending review{pendingCount !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="tabs animate-in" style={{ maxWidth: 400 }}>
          {['PENDING', 'APPROVED', 'REJECTED', ''].map((f) => (
            <button
              key={f}
              className={`tab ${filter === f ? 'tab--active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f || 'All'}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="spinner-container"><div className="spinner" /><span>Loading reviews...</span></div>
        ) : reviews.length > 0 ? (
          <div className="flex flex-col gap-2">
            {reviews.map((review) => (
              <ReviewCard key={review.review_id} review={review} onDecision={handleDecision} />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-state__icon">🎉</div>
            <div className="empty-state__title">
              {filter === 'PENDING' ? 'No pending reviews!' : 'No reviews found'}
            </div>
            <div className="empty-state__text">
              {filter === 'PENDING' ? 'All attendance cases have been reviewed.' : 'Try changing the filter.'}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
