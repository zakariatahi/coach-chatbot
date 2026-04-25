import { useState, useRef, useEffect } from 'react';

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    if (!disabled) ref.current?.focus();
  }, [disabled]);

  const submit = () => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText('');
  };

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  return (
    <div className="chat-input-area">
      <div className="chat-input-wrap">
        <textarea
          ref={ref}
          className="chat-textarea"
          rows={1}
          placeholder="Ask your coach anything…"
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={onKey}
          disabled={disabled}
        />
        <button className="chat-send-btn" onClick={submit} disabled={disabled || !text.trim()}>
          {disabled ? <div className="spinner" /> : '↑'}
        </button>
      </div>
    </div>
  );
}
