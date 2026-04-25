import { useRef, useState } from 'react';
import { uploadLog } from '../api/client';

export default function FileUpload({ onUpload, compact = false }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError]         = useState('');

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const data = await uploadLog(file);
      onUpload(data.filename);
    } catch (e) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const onInputChange = (e) => handleFile(e.target.files?.[0]);
  const onDrop = (e) => { e.preventDefault(); handleFile(e.dataTransfer.files?.[0]); };
  const onDragOver = (e) => e.preventDefault();

  if (compact) {
    return (
      <div className="chat-input-area">
        <div className="chat-input-wrap" style={{ justifyContent: 'center' }}>
          <input ref={fileRef} type="file" accept=".txt,.pdf" style={{ display:'none' }} onChange={onInputChange} />
          <p style={{ fontSize:13, color:'var(--text-dim)', marginRight:12 }}>
            📂 Upload a log to continue chatting
          </p>
          <button className="upload-btn" onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? <><div className="spinner" /> Uploading…</> : 'Browse files'}
          </button>
          {error && <span style={{ fontSize:12, color:'var(--danger)', marginLeft:8 }}>{error}</span>}
        </div>
      </div>
    );
  }

  return (
    <div className="upload-gate">
      <input ref={fileRef} type="file" accept=".txt,.pdf" style={{ display:'none' }} onChange={onInputChange} />
      <div
        className="upload-card"
        onDrop={onDrop}
        onDragOver={onDragOver}
        onClick={() => fileRef.current?.click()}
        style={{ cursor:'pointer' }}
      >
        <div className="up-icon">📂</div>
        <div className="up-title">Upload Your Daily Log</div>
        <div className="up-sub">
          Drop a <strong>.txt</strong> or <strong>.pdf</strong> file here,<br />
          or click to browse.
        </div>
        <button className="upload-btn" disabled={uploading} onClick={e => { e.stopPropagation(); fileRef.current?.click(); }}>
          {uploading ? <><div className="spinner" /> Uploading…</> : '📁 Choose file'}
        </button>
        {error && <p className="upload-progress" style={{ color:'var(--danger)' }}>{error}</p>}
        {uploading && <p className="upload-progress">Processing your file…</p>}
      </div>
    </div>
  );
}
