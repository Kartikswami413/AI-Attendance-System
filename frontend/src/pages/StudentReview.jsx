import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { studentsAPI } from '../api/client';

const TOKEN_KEY = 'veriattend_student_token';
const currentMonth = () => new Date().toISOString().slice(0, 7);

export default function StudentReview() {
  const navigate = useNavigate();
  const [month, setMonth] = useState(currentMonth());
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const studentConfig = () => ({
    headers: { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` },
  });

  const loadRecords = async (selectedMonth = month) => {
    if (!localStorage.getItem(TOKEN_KEY)) {
      navigate('/student/account');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await studentsAPI.monthlyAttendance(selectedMonth, studentConfig());
      setRecords(response.data);
    } catch (err) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        localStorage.removeItem(TOKEN_KEY);
        navigate('/student/account');
        return;
      }
      setError(err.response?.data?.detail || 'Could not load your attendance records.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRecords(); }, []);

  const bySubject = useMemo(() => records.reduce((groups, record) => {
    const name = record.subject_name || 'Unknown subject';
    groups[name] = groups[name] || [];
    groups[name].push(record);
    return groups;
  }, {}), [records]);

  const approved = records.filter((record) => record.status === 'PRESENT').length;
  const pending = records.filter((record) => record.status === 'MANUAL_REVIEW' || record.review_status === 'PENDING').length;

  return (
    <div className="app-layout">
      <header className="app-header">
        <Link to="/attendance" className="app-header__brand"><span className="app-header__title">VeriAttend</span></Link>
        <nav className="app-header__nav">
          <Link to="/student/account" className="btn btn--ghost btn--sm">My Account</Link>
          <Link to="/attendance" className="btn btn--ghost btn--sm">Attendance</Link>
        </nav>
      </header>
      <main className="app-main" style={{ maxWidth: 920, margin: '0 auto' }}>
        <div className="animate-in">
          <h1>Monthly Attendance Review</h1>
          <p className="text-muted mt-1">Your marked attendance records, grouped by subject.</p>

          <div className="card mt-3">
            <div className="flex gap-2" style={{ alignItems: 'end', flexWrap: 'wrap' }}>
              <div className="input-group" style={{ minWidth: 180, margin: 0 }}>
                <label className="input-group__label">Month</label>
                <input className="input" type="month" value={month} onChange={(event) => setMonth(event.target.value)} />
              </div>
              <button className="btn btn--primary" onClick={() => loadRecords()} disabled={loading || !month}>
                {loading ? 'Loading...' : 'Review records'}
              </button>
            </div>
          </div>

          {error && <div className="alert alert--error mt-2">⚠️ {error}</div>}
          {!loading && !error && (
            <>
              <div className="card mt-3">
                <strong>{records.length}</strong> recorded attempt{records.length === 1 ? '' : 's'} in {month};&nbsp;
                <strong>{approved}</strong> present; <strong>{pending}</strong> pending review.
                <p className="text-muted text-sm mt-1">Only successful and review-queue attempts are stored. This screen does not infer absences for sessions you did not attempt.</p>
              </div>
              {records.length === 0 ? (
                <div className="card text-center mt-3" style={{ padding: '2.5rem' }}>
                  <div style={{ fontSize: '2.5rem' }}>📅</div>
                  <h3 className="mt-1">No records for this month</h3>
                  <p className="text-muted mt-1">Try a different month after attendance has been marked.</p>
                </div>
              ) : Object.entries(bySubject).map(([subject, subjectRecords]) => (
                <section className="card mt-3" key={subject}>
                  <h3>{subject}</h3>
                  <div style={{ overflowX: 'auto' }} className="mt-2">
                    <table className="data-table">
                      <thead><tr><th>Date</th><th>Status</th><th>Verification</th><th>Confidence</th></tr></thead>
                      <tbody>{subjectRecords.map((record) => (
                        <tr key={record.attendance_id}>
                          <td>{record.date}</td>
                          <td>{record.status === 'PRESENT' ? 'Present' : 'Pending review'}</td>
                          <td>{record.verification_method === 'AUTO_HIGH_CONFIDENCE' ? 'Auto approved' : 'Manual review'}</td>
                          <td>{record.recognition_confidence == null ? '—' : `${Math.round(record.recognition_confidence * 100)}%`}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                </section>
              ))}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
