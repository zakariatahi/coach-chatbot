/* API client — all requests go through Vite proxy */

export async function apiFetch(path, opts = {}) {
  const res = await fetch(path, { credentials: 'include', ...opts });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const getMe          = ()        => apiFetch('/auth/me');
export const getAuthUrl     = ()        => apiFetch('/auth/google/url').then(d => d.url);
export const logout         = ()        => apiFetch('/auth/logout', { method: 'POST' });
export const getLogStatus   = ()        => apiFetch('/api/log-status');
export const getSessions    = ()        => apiFetch('/api/sessions');
export const createSession  = ()        => apiFetch('/api/sessions', { method: 'POST' });
export const getMessages    = (sid)     => apiFetch(`/api/sessions/${sid}/messages`);

export async function uploadLog(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/upload', { method: 'POST', credentials: 'include', body: fd });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

/**
 * POST /api/chat and consume the SSE stream.
 * onToken(text)  — called for each streaming token
 * onTool(name)   — called when a tool is used
 * onDone(answer) — called with the final full answer
 * onError(msg)   — called on error
 */
export async function streamChat({ message, session_id, onToken, onTool, onDone, onError }) {
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      onError(err.detail || 'Chat request failed');
      return;
    }
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = JSON.parse(line.slice(6));
        if (data.type === 'token')     onToken?.(data.content);
        if (data.type === 'tool')      onTool?.(data.name);
        if (data.type === 'done')      { onDone?.(data.answer); return; }
        if (data.type === 'error')     { onError?.(data.content); return; }
      }
    }
  } catch (e) {
    onError(e.message);
  }
}
