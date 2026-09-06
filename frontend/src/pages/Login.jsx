/**
 * VeriAttend — Login Page
 *
 * Teacher authentication with register/login toggle.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';

export default function Login() {
  const navigate = useNavigate();
  const [isRegister, setIsRegister] = useState(false);
  const [form, setForm] = useState({ username: '', password: '', name: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      if (isRegister) {
        await authAPI.register({ username: form.username, password: form.password, name: form.name });
        setSuccess('Account created! Please log in.');
        setIsRegister(false);
        setForm((f) => ({ ...f, password: '' }));
      } else {
        const res = await authAPI.login({ username: form.username, password: form.password });
        localStorage.setItem('veriattend_token', res.data.access_token);
        localStorage.setItem('veriattend_teacher', JSON.stringify({
          teacher_id: res.data.teacher_id,
          name: res.data.name,
        }));
        navigate('/dashboard');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-layout" style={{ justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <div className="card" style={{ maxWidth: 440, width: '90%', padding: '2.5rem' }}>
        {/* Brand */}
        <div className="text-center mb-3">
          <img src="https://i.ibb.co/YTYGn5qV/logo.png" alt="VeriAttend" style={{ width: 56, marginBottom: '0.75rem' }} />
          <h1 style={{ fontSize: '2rem' }}>
            <span style={{ background: 'linear-gradient(135deg, var(--primary-400), var(--accent-400))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              VeriAttend
            </span>
          </h1>
          <p className="text-muted text-sm mt-1">AI-Powered Attendance Platform</p>
        </div>

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${!isRegister ? 'tab--active' : ''}`}
            onClick={() => { setIsRegister(false); setError(''); setSuccess(''); }}
          >
            Login
          </button>
          <button
            className={`tab ${isRegister ? 'tab--active' : ''}`}
            onClick={() => { setIsRegister(true); setError(''); setSuccess(''); }}
          >
            Register
          </button>
        </div>

        {error && <div className="alert alert--error mb-2">⚠️ {error}</div>}
        {success && <div className="alert alert--success mb-2">✅ {success}</div>}

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div className="input-group mb-2">
              <label className="input-group__label">Full Name</label>
              <input
                className="input"
                type="text"
                placeholder="Dr. Ananya Roy"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                id="input-name"
              />
            </div>
          )}

          <div className="input-group mb-2">
            <label className="input-group__label">Username</label>
            <input
              className="input"
              type="text"
              placeholder="ananyaroy"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              required
              id="input-username"
            />
          </div>

          <div className="input-group mb-3">
            <label className="input-group__label">Password</label>
            <input
              className="input"
              type="password"
              placeholder="Enter password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              id="input-password"
            />
          </div>

          <button
            type="submit"
            className="btn btn--primary btn--full btn--lg"
            disabled={loading}
            id="btn-auth-submit"
          >
            {loading ? '...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="text-center mt-2">
          <a href="/attendance" className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Student? Go to Attendance →
          </a>
        </div>
      </div>
    </div>
  );
}
