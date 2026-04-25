import { useEffect, useRef } from 'react';
import Message from './Message';

export default function ChatWindow({ messages, user, streaming, streamingText, activeTool }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  return (
    <div className="chat-messages">
      <div className="chat-messages-inner">
        {messages.length === 0 && !streaming && (
          <div className="chat-empty">
            <div className="empty-icon">👋</div>
            <div className="empty-title">Hello, {(user.name || 'there').split(' ')[0]}!</div>
            <div className="empty-sub">
              Ask me anything about your productivity,<br />
              sleep, goals, or today's plan.
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <Message key={i} msg={m} user={user} />
        ))}

        {/* Live streaming bubble */}
        {streaming && (
          <div className="msg-row">
            <div className="msg-avatar coach-av">🧠</div>
            <div className="msg-body">
              {activeTool && (
                <span className="tool-event">🔧 Using {activeTool}…</span>
              )}
              <div className="bubble coach-bubble">
                {streamingText || <span style={{ color: 'var(--text-dim)' }}>Thinking…</span>}
                <span className="streaming-cursor" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
