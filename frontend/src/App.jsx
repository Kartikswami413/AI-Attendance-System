/**
 * VeriAttend — App Root
 *
 * Routes:
 *   /                — Redirect to attendance
 *   /login           — Teacher login/register
 *   /register        — Student registration
 *   /attendance      — Student attendance flow
 *   /dashboard       — Admin dashboard
 *   /reviews         — Manual review queue
 */

import { Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import StudentRegister from './pages/StudentRegister';
import AttendancePage from './pages/AttendancePage';
import AdminDashboard from './pages/AdminDashboard';
import ReviewQueue from './pages/ReviewQueue';
import StudentAccount from './pages/StudentAccount';
import StudentReview from './pages/StudentReview';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/attendance" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<StudentRegister />} />
      <Route path="/attendance" element={<AttendancePage />} />
      <Route path="/student/account" element={<StudentAccount />} />
      <Route path="/student/review" element={<StudentReview />} />
      <Route path="/dashboard" element={<AdminDashboard />} />
      <Route path="/reviews" element={<ReviewQueue />} />
    </Routes>
  );
}
