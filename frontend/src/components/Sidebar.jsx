import { useMemo } from 'react';
import { logout } from '../api/client';

function groupSessions(sessions) {
  const today     = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const weekAgo   = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  const groups = { Today: [], Yesterday: [], 'This week': [], Earlier: [] };
  for (const s of sessions) {
    const d = s.date || '';
    if (d === today)           groups['Today'].push(s);
    else if (d === yesterday)  groups['Yesterday'].push(s);
    else if (d >= weekAgo)     groups['This week'].push(s);
    else                       groups['Earlier'].push(s);
  }
  return groups;
}

export default function Sidebar({ sessions, currentSid, user, onSelectSession, onNewChat, onLogout }) {
  const groups = useMemo(() => groupSessions(sessions), [sessions]);

  const handleLogout = async () => {
    await logout().catch(() => {});
    onLogout();
  };

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <span className="logo-icon">🧠</span>
        <div>
          <div className="logo-name">COACH AI</div>
          <div className="logo-sub">Personal Productivity Coach</div>
        </div>
      </div>

      {/* New chat */}
      <button className="sidebar-new-btn" onClick={onNewChat}>
        ＋ New Chat
      </button>

      {/* Sessions */}
      <div className="sidebar-sessions">
        {sessions.length === 0 && (
          <div className="sidebar-empty">
            No conversations yet.<br />Start a new chat!
          </div>
        )}
        {Object.entries(groups).map(([group, items]) =>
          items.length === 0 ? null : (
            <div key={group}>
              <div className="session-group-label">{group}</div>
              {items.map(s => (
                <div
                  key={s.session_id}
                  className={`session-item ${s.session_id === currentSid ? 'active' : ''}`}
                  onClick={() => onSelectSession(s.session_id)}
                  title={`${s.date} · ${s.total_messages} messages`}
                >
                  <span className="session-icon">
                    {s.session_id === currentSid ? '💬' : '·'}
                  </span>
                  <span className="session-title">
                    {s.title || 'New Chat'}
                  </span>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* User card */}
      <div className="sidebar-user">
        {user.picture
          ? <img className="user-avatar" src={user.picture} alt={user.name} />
          : <div className="user-avatar-placeholder">{(user.name || 'U')[0].toUpperCase()}</div>
        }
        <div className="user-info">
          <div className="user-name">{user.name}</div>
          <div className="user-email">{user.email}</div>
        </div>
        <button className="logout-btn" onClick={handleLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
