import { useState, useEffect, useCallback } from 'react';
import Sidebar    from '../components/Sidebar';
import ChatWindow from '../components/ChatWindow';
import ChatInput  from '../components/ChatInput';
import FileUpload from '../components/FileUpload';
import { getSessions, createSession, getMessages, getLogStatus, streamChat } from '../api/client';

export default function Chat({ user, onLogout }) {
  const [sessions,       setSessions]       = useState([]);
  const [currentSid,     setCurrentSid]     = useState(null);
  const [messages,       setMessages]       = useState([]);
  const [sessionTitle,   setSessionTitle]   = useState('New Chat');
  const [logStatus,      setLogStatus]      = useState({ uploaded: false, filename: '' });
  const [streaming,      setStreaming]      = useState(false);
  const [streamingText,  setStreamingText]  = useState('');
  const [activeTool,     setActiveTool]     = useState(null);
  const [viewOnly,       setViewOnly]       = useState(false); // viewing history without log

  // load sessions + log status on mount
  useEffect(() => {
    Promise.all([getSessions(), getLogStatus()])
      .then(([s, log]) => { setSessions(s); setLogStatus(log); })
      .catch(console.error);
  }, []);

  const refreshSessions = () => getSessions().then(setSessions).catch(console.error);

  const handleSelectSession = useCallback(async (sid) => {
    try {
      const data = await getMessages(sid);
      setCurrentSid(sid);
      setMessages(data.messages || []);
      setSessionTitle(data.title || 'Chat');
      setStreamingText('');
      // if no log uploaded, this session is view-only
      setViewOnly(!logStatus.uploaded);
    } catch (e) { console.error(e); }
  }, [logStatus.uploaded]);

  const handleNewChat = useCallback(async () => {
    try {
      const { session_id } = await createSession();
      setCurrentSid(session_id);
      setMessages([]);
      setSessionTitle('New Chat');
      setStreamingText('');
      setViewOnly(false);
      await refreshSessions();
    } catch (e) { console.error(e); }
  }, []);

  const handleUpload = useCallback((filename) => {
    setLogStatus({ uploaded: true, filename });
    setViewOnly(false);
    // Auto-create a new session on upload
    handleNewChat();
  }, [handleNewChat]);

  const handleSend = useCallback(async (text) => {
    if (!currentSid || streaming) return;

    const userMsg = { role: 'human', message: text, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setStreaming(true);
    setStreamingText('');
    setActiveTool(null);

    // Update title from first message
    if (messages.length === 0) {
      setSessionTitle(text.slice(0, 55));
      await refreshSessions();
    }

    await streamChat({
      message: text,
      session_id: currentSid,
      onToken: (t) => setStreamingText(prev => prev + t),
      onTool:  (n) => setActiveTool(n),
      onDone:  (answer) => {
        const coachMsg = { role: 'coach', message: answer, timestamp: new Date().toISOString() };
        setMessages(prev => [...prev, coachMsg]);
        setStreaming(false);
        setStreamingText('');
        setActiveTool(null);
        refreshSessions();
      },
      onError: (err) => {
        const errMsg = { role: 'coach', message: `⚠️ ${err}`, timestamp: new Date().toISOString() };
        setMessages(prev => [...prev, errMsg]);
        setStreaming(false);
        setStreamingText('');
        setActiveTool(null);
      },
    });
  }, [currentSid, streaming, messages.length]);

  const showUploadGate = !logStatus.uploaded && !currentSid;
  const showViewOnly   = currentSid && !logStatus.uploaded;

  return (
    <div className="app-shell">
      <Sidebar
        sessions={sessions}
        currentSid={currentSid}
        user={user}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onLogout={onLogout}
      />

      <div className="chat-area">
        {/* Header */}
        <div className="chat-header">
          <span className="header-icon">🧠</span>
          <span>{sessionTitle}</span>
          {viewOnly && <span className="header-badge">📖 History</span>}
          {logStatus.uploaded && (
            <span className="header-file">📂 {logStatus.filename}</span>
          )}
        </div>

        {/* Body */}
        {showUploadGate ? (
          <FileUpload onUpload={handleUpload} />
        ) : (
          <>
            <ChatWindow
              messages={messages}
              user={user}
              streaming={streaming}
              streamingText={streamingText}
              activeTool={activeTool}
            />
            {showViewOnly ? (
              <FileUpload compact onUpload={handleUpload} />
            ) : (
              <ChatInput onSend={handleSend} disabled={streaming} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
