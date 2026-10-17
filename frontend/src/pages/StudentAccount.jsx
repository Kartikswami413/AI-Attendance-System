import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { studentsAPI } from '../api/client';

const TOKEN_KEY = 'veriattend_student_token';

export default function StudentAccount() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [login, setLogin] = useState({ student_code: '', password: '' });
  const [confirm, setConfirm] = useState({ password: '', confirmation: '' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (localStorage.getItem(TOKEN_KEY)) loadProfile(); }, []);
  const studentConfig = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` } });
  const loadProfile = async () => {
    try { const res = await studentsAPI.me({ ...studentConfig() }); setProfile(res.data); }
    catch { localStorage.removeItem(TOKEN_KEY); }
  };
  const handleLogin = async (event) => {
    event.preventDefault(); setLoading(true); setError('');
    try {
      const res = await studentsAPI.login(login);
      localStorage.setItem(TOKEN_KEY, res.data.access_token);
      await loadProfile();
    } catch (err) { setError(err.response?.data?.detail || 'Could not sign in.'); }
    finally { setLoading(false); }
  };
  const handleDeregister = async (event) => {
    event.preventDefault(); setLoading(true); setError('');
    try {
      // The general client only sends teacher auth; explicitly scope this request to student auth.
      const res = await studentsAPI.deregister(confirm, studentConfig());
      localStorage.removeItem(TOKEN_KEY); setProfile(null); setMessage(res.data.message);
    } catch (err) { setError(err.response?.data?.detail || 'Deregistration failed.'); }
    finally { setLoading(false); }
  };
  return <div className="app-layout"><header className="app-header"><a href="/attendance" className="app-header__brand"><span className="app-header__title">VeriAttend</span></a></header>
    <main className="app-main" style={{ maxWidth: 640, margin: '0 auto' }}><div className="animate-in"><h1>Student Account</h1>
      {error && <div className="alert alert--error mb-2">⚠️ {error}</div>}{message && <div className="alert alert--success mb-2">✅ {message}</div>}
      {!profile && <form className="card" onSubmit={handleLogin}><h3 className="mb-2">Sign in to manage your account</h3><div className="input-group mb-2"><label className="input-group__label">Student ID</label><input className="input" required value={login.student_code} onChange={e => setLogin({ ...login, student_code: e.target.value })} /></div><div className="input-group mb-2"><label className="input-group__label">Password</label><input className="input" type="password" required value={login.password} onChange={e => setLogin({ ...login, password: e.target.value })} /></div><button className="btn btn--primary btn--full" disabled={loading}>{loading ? 'Signing in...' : 'Sign In'}</button></form>}
      {profile && <><div className="card mb-3"><h3>{profile.name}</h3><p className="text-muted">{profile.student_code} · {profile.email || 'No email saved'}</p><p className="text-sm mt-1">Status: <strong>{profile.account_status}</strong></p><button className="btn btn--primary mt-2" onClick={() => navigate('/student/review')}>Review my monthly attendance</button></div><form className="card" onSubmit={handleDeregister}><h3>⚠️ Deregister / Delete Account</h3><p className="text-muted text-sm mt-1">This permanently deactivates your account, removes face and voice biometric data, and removes active subject enrollments. Historical attendance is retained for institutional reports.</p><div className="input-group mt-2"><label className="input-group__label">Current password</label><input className="input" type="password" required value={confirm.password} onChange={e => setConfirm({ ...confirm, password: e.target.value })} /></div><div className="input-group mt-2"><label className="input-group__label">Type DEREGISTER to confirm</label><input className="input" required value={confirm.confirmation} onChange={e => setConfirm({ ...confirm, confirmation: e.target.value })} /></div><button className="btn btn--danger btn--full mt-2" disabled={loading}>{loading ? 'Deregistering...' : 'Deregister Account'}</button></form></>}
      <button className="btn btn--ghost mt-3" onClick={() => navigate('/attendance')}>← Back to attendance</button></div></main></div>;
}
