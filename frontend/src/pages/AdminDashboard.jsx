/**
 * VeriAttend — Admin Dashboard
 *
 * Dashboard with:
 * - Stats cards (total students, present today, absent, pending reviews)
 * - Attendance table with search/filter
 * - Session management
 * - Subject management
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI, enrollmentAPI, sessionsAPI, studentsAPI } from '../api/client';

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [teacher, setTeacher] = useState(null);
  const [stats, setStats] = useState(null);
  const [records, setRecords] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [students, setStudents] = useState([]);
  const [subjectRosters, setSubjectRosters] = useState({});
  const [studentToEnroll, setStudentToEnroll] = useState({});
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  // Filters
  const [filters, setFilters] = useState({ subject_id: '', date: '', student_name: '', status_filter: '' });

  // Create session form
  const [sessionForm, setSessionForm] = useState({ name: '', subject_id: '', date: '', start_time: '', end_time: '' });

  // Create subject form
  const [subjectForm, setSubjectForm] = useState({ subject_code: '', name: '', section: '' });
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  useEffect(() => {
    const stored = localStorage.getItem('veriattend_teacher');
    if (!stored) { navigate('/login'); return; }
    setTeacher(JSON.parse(stored));
    loadData();
  }, [navigate]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, recordsRes, subjectsRes, sessionsRes, studentsRes] = await Promise.all([
        adminAPI.dashboard(),
        adminAPI.getAttendance({ limit: 50 }),
        adminAPI.listSubjects(),
        sessionsAPI.list(),
        adminAPI.listStudents(),
      ]);
      setStats(statsRes.data);
      setRecords(recordsRes.data);
      setSubjects(subjectsRes.data);
      setSessions(sessionsRes.data);
      setStudents(studentsRes.data);
      const rosterResponses = await Promise.all(
        subjectsRes.data.map(async (subject) => [subject.subject_id, (await enrollmentAPI.getStudents(subject.subject_id)).data])
      );
      setSubjectRosters(Object.fromEntries(rosterResponses));
    } catch (err) {
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilter = async () => {
    try {
      const params = {};
      if (filters.subject_id) params.subject_id = filters.subject_id;
      if (filters.date) params.date = filters.date;
      if (filters.student_name) params.student_name = filters.student_name;
      if (filters.status_filter) params.status_filter = filters.status_filter;
      const res = await adminAPI.getAttendance(params);
      setRecords(res.data);
    } catch (err) {
      console.error('Filter error:', err);
    }
  };

  const handleCreateSession = async (e) => {
    e.preventDefault();
    setFormError(''); setFormSuccess('');
    try {
      const payload = {
        ...sessionForm,
        subject_id: Number(sessionForm.subject_id),
        // Keep local wall-clock times. The backend stores session windows as local
        // values so the teacher sees the same time they selected in the dashboard.
        start_time: `${sessionForm.date}T${sessionForm.start_time}`,
        end_time: `${sessionForm.date}T${sessionForm.end_time}`,
      };
      await sessionsAPI.create(payload);
      setFormSuccess('Session created!');
      setSessionForm({ name: '', subject_id: '', date: '', start_time: '', end_time: '' });
      loadData();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create session.');
    }
  };

  const handleCreateSubject = async (e) => {
    e.preventDefault();
    setFormError(''); setFormSuccess('');
    try {
      await adminAPI.createSubject(subjectForm);
      setFormSuccess('Subject created!');
      setSubjectForm({ subject_code: '', name: '', section: '' });
      loadData();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create subject.');
    }
  };

  const handleToggleSession = async (sessionId, isActive) => {
    try {
      await sessionsAPI.toggle(sessionId, !isActive);
      loadData();
    } catch (err) {
      console.error('Toggle error:', err);
    }
  };

  const handleDeleteSession = async (sessionId, name) => {
    if (!window.confirm(`Delete "${name}" from the sessions list? Attendance records will be retained.`)) return;
    try {
      await sessionsAPI.remove(sessionId);
      setFormSuccess('Session removed. Existing attendance records were kept.');
      loadData();
    } catch (err) { setFormError(err.response?.data?.detail || 'Could not delete session.'); }
  };

  const handleEnrollStudent = async (subject) => {
    const studentId = Number(studentToEnroll[subject.subject_id]);
    if (!studentId) return;
    setFormError(''); setFormSuccess('');
    try {
      await enrollmentAPI.enroll({ student_id: studentId, subject_code: subject.subject_code });
      setStudentToEnroll((current) => ({ ...current, [subject.subject_id]: '' }));
      setFormSuccess('Student enrolled successfully.');
      loadData();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Could not enroll student.');
    }
  };

  const handleRemoveFromClass = async (subject, student) => {
    if (!window.confirm(`Remove ${student.name} from ${subject.name}? They will no longer be able to mark attendance for this subject.`)) return;
    setFormError(''); setFormSuccess('');
    try {
      await enrollmentAPI.unenroll(student.student_id, subject.subject_id);
      setFormSuccess(`${student.name} was removed from ${subject.name}.`);
      loadData();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Could not remove the student from this subject.');
    }
  };

  const handleEraseFace = async (subject, student) => {
    const confirmed = window.confirm(
      `Permanently erase ${student.name}'s enrolled face data and remove them from ${subject.name}? This cannot be undone; they must register their face again to use attendance.`
    );
    if (!confirmed) return;
    setFormError(''); setFormSuccess('');
    try {
      await studentsAPI.removeFace(student.student_id, subject.subject_id);
      setFormSuccess(`Face data erased and ${student.name} removed from ${subject.name}.`);
      loadData();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Could not erase the face data.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('veriattend_token');
    localStorage.removeItem('veriattend_teacher');
    navigate('/login');
  };

  if (loading) {
    return (
      <div className="app-layout">
        <div className="spinner-container" style={{ minHeight: '100vh' }}>
          <div className="spinner" />
          <span>Loading dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="app-layout">
      <header className="app-header">
        <a href="/dashboard" className="app-header__brand">
          <img src="https://i.ibb.co/YTYGn5qV/logo.png" alt="" className="app-header__logo" />
          <span className="app-header__title">VeriAttend</span>
        </a>
        <nav className="app-header__nav">
          <span className="text-sm text-muted">👋 {teacher?.name}</span>
          <a href="/reviews" className="btn btn--ghost btn--sm">📋 Reviews</a>
          <button className="btn btn--ghost btn--sm" onClick={handleLogout}>Logout</button>
        </nav>
      </header>

      <main className="app-main">
        {/* Tabs */}
        <div className="tabs" style={{ maxWidth: 600 }}>
          {['overview', 'attendance', 'sessions', 'subjects', 'students'].map((tab) => (
            <button key={tab} className={`tab ${activeTab === tab ? 'tab--active' : ''}`}
              onClick={() => setActiveTab(tab)}>
              {tab === 'overview' ? '📊 Overview' : tab === 'attendance' ? '📋 Attendance' :
                tab === 'sessions' ? '📅 Sessions' : tab === 'subjects' ? '📚 Subjects' : '👥 Students'}
            </button>
          ))}
        </div>

        {formError && <div className="alert alert--error mb-2">⚠️ {formError}</div>}
        {formSuccess && <div className="alert alert--success mb-2">✅ {formSuccess}</div>}

        {/* Overview Tab */}
        {activeTab === 'overview' && stats && (
          <div className="animate-in">
            <div className="grid-4 mb-3">
              <div className="stat-card">
                <div className="stat-card__icon stat-card__icon--primary">👥</div>
                <div><div className="stat-card__value">{stats.total_students}</div><div className="stat-card__label">Total Students</div></div>
              </div>
              <div className="stat-card">
                <div className="stat-card__icon stat-card__icon--success">✅</div>
                <div><div className="stat-card__value">{stats.present_today}</div><div className="stat-card__label">Present Today</div></div>
              </div>
              <div className="stat-card">
                <div className="stat-card__icon stat-card__icon--error">❌</div>
                <div><div className="stat-card__value">{stats.absent_today}</div><div className="stat-card__label">Absent Today</div></div>
              </div>
              <div className="stat-card">
                <div className="stat-card__icon stat-card__icon--warning">📋</div>
                <div><div className="stat-card__value">{stats.pending_reviews}</div><div className="stat-card__label">Pending Reviews</div></div>
              </div>
            </div>

            {/* Recent Attendance */}
            <h3 className="mb-2">Recent Attendance</h3>
            {records.length > 0 ? (
              <div className="table-container">
                <table className="table">
                  <thead><tr>
                    <th>Student</th><th>Subject</th><th>Date</th><th>Time</th>
                    <th>Confidence</th><th>Liveness</th><th>Status</th>
                  </tr></thead>
                  <tbody>
                    {records.slice(0, 10).map((r) => (
                      <tr key={r.attendance_id}>
                        <td><strong>{r.student_name}</strong><br /><span className="text-sm text-muted">{r.student_code}</span></td>
                        <td>{r.subject_name}</td>
                        <td>{r.date}</td>
                        <td>{new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                        <td>
                          <span style={{ fontWeight: 600 }}>{r.recognition_confidence ? `${(r.recognition_confidence * 100).toFixed(0)}%` : '—'}</span>
                        </td>
                        <td><span className={`badge ${r.liveness_status === 'PASS' ? 'badge--success' : 'badge--neutral'}`}>{r.liveness_status}</span></td>
                        <td><span className={`badge ${r.status === 'PRESENT' ? 'badge--success' : r.status === 'MANUAL_REVIEW' ? 'badge--warning' : 'badge--error'}`}>{r.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state"><div className="empty-state__icon">📊</div><div className="empty-state__title">No attendance records yet</div></div>
            )}
          </div>
        )}

        {/* Attendance Tab */}
        {activeTab === 'attendance' && (
          <div className="animate-in">
            <h3 className="mb-2">Attendance Records</h3>
            <div className="filter-bar">
              <div className="input-group">
                <label className="input-group__label">Subject</label>
                <select className="input" value={filters.subject_id} onChange={(e) => setFilters({ ...filters, subject_id: e.target.value })}>
                  <option value="">All Subjects</option>
                  {subjects.map((s) => <option key={s.subject_id} value={s.subject_id}>{s.name}</option>)}
                </select>
              </div>
              <div className="input-group">
                <label className="input-group__label">Date</label>
                <input className="input" type="date" value={filters.date} onChange={(e) => setFilters({ ...filters, date: e.target.value })} />
              </div>
              <div className="input-group">
                <label className="input-group__label">Student</label>
                <input className="input" placeholder="Search name..." value={filters.student_name} onChange={(e) => setFilters({ ...filters, student_name: e.target.value })} />
              </div>
              <div className="input-group">
                <label className="input-group__label">Status</label>
                <select className="input" value={filters.status_filter} onChange={(e) => setFilters({ ...filters, status_filter: e.target.value })}>
                  <option value="">All</option>
                  <option value="PRESENT">Present</option>
                  <option value="MANUAL_REVIEW">Manual Review</option>
                  <option value="REJECTED">Rejected</option>
                </select>
              </div>
              <button className="btn btn--primary btn--sm" onClick={handleFilter}>🔍 Filter</button>
            </div>

            {records.length > 0 ? (
              <div className="table-container">
                <table className="table">
                  <thead><tr>
                    <th>Student</th><th>Subject</th><th>Date</th><th>Time</th>
                    <th>Confidence</th><th>Liveness</th><th>Status</th><th>Review</th>
                  </tr></thead>
                  <tbody>
                    {records.map((r) => (
                      <tr key={r.attendance_id}>
                        <td><strong>{r.student_name}</strong><br /><span className="text-sm text-muted">{r.student_code}</span></td>
                        <td>{r.subject_name}</td>
                        <td>{r.date}</td>
                        <td>{new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                        <td>{r.recognition_confidence ? `${(r.recognition_confidence * 100).toFixed(0)}%` : '—'}</td>
                        <td><span className={`badge ${r.liveness_status === 'PASS' ? 'badge--success' : 'badge--neutral'}`}>{r.liveness_status}</span></td>
                        <td><span className={`badge ${r.status === 'PRESENT' ? 'badge--success' : r.status === 'MANUAL_REVIEW' ? 'badge--warning' : 'badge--error'}`}>{r.status}</span></td>
                        <td><span className={`badge ${r.review_status === 'APPROVED' ? 'badge--success' : r.review_status === 'PENDING' ? 'badge--warning' : 'badge--neutral'}`}>{r.review_status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state"><div className="empty-state__icon">📋</div><div className="empty-state__title">No records found</div></div>
            )}
          </div>
        )}

        {/* Sessions Tab */}
        {activeTab === 'sessions' && (
          <div className="animate-in">
            <div className="page-header">
              <h3>📅 Attendance Sessions</h3>
            </div>

            {/* Create Session Form */}
            <div className="card mb-3">
              <h4 className="mb-2">Create New Session</h4>
              <form onSubmit={handleCreateSession}>
                <div className="grid-2 mb-2">
                  <div className="input-group">
                    <label className="input-group__label">Session Name *</label>
                    <input className="input" required placeholder="Morning Attendance" value={sessionForm.name}
                      onChange={(e) => setSessionForm({ ...sessionForm, name: e.target.value })} />
                  </div>
                  <div className="input-group">
                    <label className="input-group__label">Subject *</label>
                    <select className="input" required value={sessionForm.subject_id}
                      onChange={(e) => setSessionForm({ ...sessionForm, subject_id: e.target.value })}>
                      <option value="">Select...</option>
                      {subjects.map((s) => <option key={s.subject_id} value={s.subject_id}>{s.name} ({s.subject_code})</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid-3 mb-2">
                  <div className="input-group">
                    <label className="input-group__label">Date *</label>
                    <input className="input" type="date" required value={sessionForm.date}
                      onChange={(e) => setSessionForm({ ...sessionForm, date: e.target.value })} />
                  </div>
                  <div className="input-group">
                    <label className="input-group__label">Start Time *</label>
                    <input className="input" type="time" required value={sessionForm.start_time}
                      onChange={(e) => setSessionForm({ ...sessionForm, start_time: e.target.value })} />
                  </div>
                  <div className="input-group">
                    <label className="input-group__label">End Time *</label>
                    <input className="input" type="time" required value={sessionForm.end_time}
                      onChange={(e) => setSessionForm({ ...sessionForm, end_time: e.target.value })} />
                  </div>
                </div>
                <button type="submit" className="btn btn--primary">➕ Create Session</button>
              </form>
            </div>

            {/* Sessions List */}
            {sessions.length > 0 ? (
              <div className="table-container">
                <table className="table">
                  <thead><tr><th>Name</th><th>Subject</th><th>Date</th><th>Time</th><th>Status</th><th>Action</th></tr></thead>
                  <tbody>
                    {sessions.map((s) => (
                      <tr key={s.session_id}>
                        <td><strong>{s.name}</strong></td>
                        <td>{s.subject_name}</td>
                        <td>{s.date}</td>
                        <td>{new Date(s.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} — {new Date(s.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                        <td><span className={`badge ${s.is_active ? 'badge--success' : 'badge--neutral'}`}>{s.is_active ? 'Active' : 'Inactive'}</span></td>
                        <td><div className="flex gap-1"><button className={`btn btn--sm ${s.is_active ? 'btn--danger' : 'btn--success'}`}
                          onClick={() => handleToggleSession(s.session_id, s.is_active)}>
                          {s.is_active ? 'Deactivate' : 'Activate'}
                        </button><button className="btn btn--danger btn--sm" onClick={() => handleDeleteSession(s.session_id, s.name)}>Delete</button></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state"><div className="empty-state__icon">📅</div><div className="empty-state__title">No sessions yet</div></div>
            )}
          </div>
        )}

        {/* Subjects Tab */}
        {activeTab === 'subjects' && (
          <div className="animate-in">
            <div className="page-header"><h3>📚 Subjects</h3></div>

            <div className="card mb-3">
              <h4 className="mb-2">Create New Subject</h4>
              <form onSubmit={handleCreateSubject} className="grid-3" style={{ alignItems: 'end' }}>
                <div className="input-group">
                  <label className="input-group__label">Code *</label>
                  <input className="input" required placeholder="CS101" value={subjectForm.subject_code}
                    onChange={(e) => setSubjectForm({ ...subjectForm, subject_code: e.target.value })} />
                </div>
                <div className="input-group">
                  <label className="input-group__label">Name *</label>
                  <input className="input" required placeholder="Data Structures" value={subjectForm.name}
                    onChange={(e) => setSubjectForm({ ...subjectForm, name: e.target.value })} />
                </div>
                <div className="input-group">
                  <label className="input-group__label">Section *</label>
                  <div className="flex gap-1">
                    <input className="input" required placeholder="A" value={subjectForm.section}
                      onChange={(e) => setSubjectForm({ ...subjectForm, section: e.target.value })} style={{ flex: 1 }} />
                    <button type="submit" className="btn btn--primary btn--sm">➕ Create</button>
                  </div>
                </div>
              </form>
            </div>

            {subjects.length > 0 ? (
              <div className="grid-2">
                {subjects.map((s) => (
                  <div className="card" key={s.subject_id}>
                    <h4>{s.name}</h4>
                    <p className="text-sm text-muted mt-1">
                      Code: <span className="badge badge--primary">{s.subject_code}</span> &middot; Section: {s.section}
                    </p>
                    <p className="text-sm mt-1">👥 {s.enrolled_count} enrolled</p>
                    <div className="flex gap-1 mt-2">
                      <select
                        className="input"
                        value={studentToEnroll[s.subject_id] || ''}
                        onChange={(e) => setStudentToEnroll({ ...studentToEnroll, [s.subject_id]: e.target.value })}
                        aria-label={`Student to enroll in ${s.name}`}
                        style={{ flex: 1 }}
                      >
                        <option value="">Enroll a registered student...</option>
                        {students.map((student) => (
                          <option key={student.student_id} value={student.student_id}>
                            {student.student_code} — {student.name}{student.is_active === false ? ' (Deregistered)' : student.has_face_embedding ? '' : ' (face not enrolled)'}
                          </option>
                        ))}
                      </select>
                      <button
                        className="btn btn--primary btn--sm"
                        onClick={() => handleEnrollStudent(s)}
                        disabled={!studentToEnroll[s.subject_id]}
                      >
                        Enroll
                      </button>
                    </div>
                    <div className="mt-2">
                      <p className="text-sm text-muted mb-1">Class roster — administrator controls</p>
                      {(subjectRosters[s.subject_id] || []).length > 0 ? (
                        <div className="flex flex-col gap-1">
                          {subjectRosters[s.subject_id].map((student) => (
                            <div key={student.student_id} className="flex gap-1" style={{ alignItems: 'center', justifyContent: 'space-between' }}>
                              <span className="text-sm">
                                {student.student_code} — {student.name} {!student.has_face_embedding && '(no face enrolled)'}
                              </span>
                              <div className="flex gap-1">
                                <button className="btn btn--secondary btn--sm" onClick={() => handleRemoveFromClass(s, student)}>
                                  Remove from class
                                </button>
                                <button className="btn btn--danger btn--sm" onClick={() => handleEraseFace(s, student)}>
                                  Erase face
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted">No students enrolled in this subject.</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state"><div className="empty-state__icon">📚</div><div className="empty-state__title">No subjects yet</div></div>
            )}
          </div>
        )}

        {activeTab === 'students' && (
          <div className="animate-in">
            <div className="page-header"><h3>👥 Student Information</h3></div>
            <p className="text-muted mb-2">Administrator view. Passwords and face vectors are never displayed or recoverable.</p>
            {students.length > 0 ? (
              <div className="table-container">
                <table className="table">
                  <thead><tr><th>Student ID</th><th>Name</th><th>Email</th><th>Department / Year</th><th>Face enrollment</th><th>Account</th></tr></thead>
                  <tbody>
                    {students.map((student) => (
                      <tr key={student.student_id}>
                        <td><strong>{student.student_code}</strong></td>
                        <td>{student.name}</td>
                        <td>{student.email || '—'}</td>
                        <td>{student.department || '—'}{student.year ? ` / ${student.year}` : ''}</td>
                        <td><span className={`badge ${student.has_face_embedding ? 'badge--success' : 'badge--neutral'}`}>{student.has_face_embedding ? 'Enrolled' : 'Not enrolled'}</span></td>
                        <td><span className={`badge ${student.is_active ? 'badge--success' : 'badge--error'}`}>{student.account_status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state"><div className="empty-state__icon">👥</div><div className="empty-state__title">No students registered yet</div></div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
