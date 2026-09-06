/**
 * VeriAttend — Status Display Component
 *
 * Animated status indicator with icon, text, and visual type.
 */

export default function StatusDisplay({ icon, text, type = 'idle', subtext }) {
  const dotClass = {
    idle: 'status-indicator__dot--idle',
    processing: 'status-indicator__dot--processing',
    success: 'status-indicator__dot--active',
    warning: 'status-indicator__dot--active',
    error: 'status-indicator__dot--error',
  }[type] || 'status-indicator__dot--idle';

  return (
    <div className="status-indicator animate-in">
      <div className={`status-indicator__dot ${dotClass}`} />
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>{icon}</span>
          <span style={{ fontWeight: 500 }}>{text}</span>
        </div>
        {subtext && (
          <div className="text-sm text-muted mt-1">{subtext}</div>
        )}
      </div>
    </div>
  );
}
