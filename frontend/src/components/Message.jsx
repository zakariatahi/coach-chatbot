import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function Message({ msg, user }) {
  const isUser = msg.role === 'human';
  const ts = msg.timestamp ? msg.timestamp.slice(11, 16) : '';

  return (
    <div className={`msg-row ${isUser ? 'user' : ''}`}>
      {isUser ? (
        user.picture
          ? <img className="msg-avatar user-av" src={user.picture} alt={user.name} />
          : <div className="msg-avatar user-av-placeholder">{(user.name || 'U')[0].toUpperCase()}</div>
      ) : (
        <div className="msg-avatar coach-av">🧠</div>
      )}

      <div className="msg-body">
        <div className={`bubble ${isUser ? 'user-bubble' : 'coach-bubble'}`}>
          {isUser
            ? msg.message
            : <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.message}</ReactMarkdown>
          }
        </div>
        <div className="msg-meta">
          {isUser ? ts : `COACH · ${ts}`}
        </div>
      </div>
    </div>
  );
}
