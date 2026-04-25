"""FastAPI backend for COACH AI."""

import os, sys, io, json, uuid, asyncio, threading
import queue as sync_queue
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from pymongo import DESCENDING
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage

from db import get_conversations_col, find_or_create_user
from backend.auth import get_google_auth_url, handle_oauth_callback, create_jwt, decode_jwt
from backend.coach_engine import build_executor
from Coach import UserProfile

load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app = FastAPI(title="COACH AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory caches (reset on server restart) ─────────────────────────────
_user_logs:      dict[str, dict] = {}   # user_id → {content, filename}
_user_executors: dict[str, object] = {} # user_id → AgentExecutor
_user_histories: dict[str, list]  = {}  # user_id → chat_history


# ── Auth dependency ────────────────────────────────────────────────────────
def get_current_user(request: Request) -> dict:
    token = request.cookies.get("coach_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    return payload


# ═══════════════════════════════════════════════════════════════════════════
# Auth routes
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/auth/google/url")
def google_url():
    return {"url": get_google_auth_url()}


@app.get("/auth/google/callback")
async def google_callback(code: str, state: str):
    user_info = await handle_oauth_callback(code, state)
    if not user_info:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=auth_failed")

    user_id = find_or_create_user(user_info["email"])
    token = create_jwt({
        "user_id": user_id,
        "email":   user_info.get("email", ""),
        "name":    user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
    })
    redirect = RedirectResponse(FRONTEND_URL)
    redirect.set_cookie(
        "coach_token", token,
        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7
    )
    return redirect


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("coach_token")
    return {"ok": True}


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {k: v for k, v in user.items() if k != "exp"}


# ═══════════════════════════════════════════════════════════════════════════
# Log upload
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/upload")
async def upload_log(file: UploadFile = File(...), user=Depends(get_current_user)):
    raw = await file.read()
    ext = file.filename.lower().rsplit(".", 1)[-1]
    if ext == "txt":
        text = raw.decode("utf-8", errors="replace")
    elif ext == "pdf":
        from pypdf import PdfReader
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
    else:
        raise HTTPException(400, "Only .txt and .pdf files are supported")

    uid = user["user_id"]
    _user_logs[uid] = {"content": text, "filename": file.filename}
    _user_executors.pop(uid, None)
    _user_histories.pop(uid, None)
    return {"ok": True, "filename": file.filename}


@app.get("/api/log-status")
def log_status(user=Depends(get_current_user)):
    uid = user["user_id"]
    if uid in _user_logs:
        return {"uploaded": True, "filename": _user_logs[uid]["filename"]}
    return {"uploaded": False}


# ═══════════════════════════════════════════════════════════════════════════
# Sessions
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/sessions")
def list_sessions(user=Depends(get_current_user)):
    docs = list(
        get_conversations_col().find(
            {"user_id": user["user_id"]},
            {"session_id": 1, "title": 1, "date": 1, "total_messages": 1, "_id": 0},
        ).sort("last_updated", DESCENDING)
    )
    return docs


@app.post("/api/sessions")
def create_session(user=Depends(get_current_user)):
    sid = str(uuid.uuid4())[:8]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    get_conversations_col().insert_one({
        "session_id": sid,
        "user_id":    user["user_id"],
        "date":       datetime.now().strftime("%Y-%m-%d"),
        "started_at": now, "last_updated": now,
        "title": "New Chat", "messages": [], "total_messages": 0,
    })
    return {"session_id": sid}


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str, user=Depends(get_current_user)):
    doc = get_conversations_col().find_one(
        {"session_id": session_id, "user_id": user["user_id"]}
    )
    if not doc:
        raise HTTPException(404, "Session not found")
    return {"messages": doc.get("messages", []), "title": doc.get("title", ""), "date": doc.get("date", "")}


# ═══════════════════════════════════════════════════════════════════════════
# Chat — SSE streaming
# ═══════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: str


@app.post("/api/chat")
async def chat(body: ChatRequest, user=Depends(get_current_user)):
    uid = user["user_id"]

    if uid not in _user_logs:
        raise HTTPException(400, "No log uploaded. Please upload your daily log first.")

    log_info = _user_logs[uid]
    profile  = UserProfile(user_id=uid)

    if uid not in _user_executors:
        _user_executors[uid] = build_executor(log_info["content"], profile)
        _user_histories[uid] = []

    executor     = _user_executors[uid]
    chat_history = _user_histories[uid]

    # Persist user message
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    get_conversations_col().update_one(
        {"session_id": body.session_id},
        {"$push": {"messages": {"timestamp": ts, "role": "human", "message": body.message}},
         "$inc": {"total_messages": 1}, "$set": {"last_updated": ts}},
    )
    doc = get_conversations_col().find_one({"session_id": body.session_id}, {"total_messages": 1})
    if doc and doc.get("total_messages", 0) <= 1:
        get_conversations_col().update_one(
            {"session_id": body.session_id},
            {"$set": {"title": body.message[:55]}}
        )

    # SSE streaming via thread + queue
    token_queue: sync_queue.Queue = sync_queue.Queue()

    class StreamHandler(BaseCallbackHandler):
        def on_llm_new_token(self, token: str, **kwargs):
            token_queue.put({"type": "token", "content": token})

        def on_tool_start(self, serialized, input_str, **kwargs):
            token_queue.put({"type": "tool", "name": serialized.get("name", "tool")})

        def on_agent_finish(self, finish, **kwargs):
            token_queue.put({"type": "finish", "output": finish.return_values.get("output", "")})

    handler = StreamHandler()

    def run_agent():
        try:
            result = executor.invoke(
                {"input": body.message, "chat_history": chat_history,
                 "user_profile": profile.to_prompt_string()},
                config={"callbacks": [handler]},
            )
            token_queue.put({"type": "done", "answer": result["output"]})
        except Exception as e:
            token_queue.put({"type": "error", "content": str(e)})

    threading.Thread(target=run_agent, daemon=True).start()

    loop = asyncio.get_event_loop()

    async def event_stream():
        full_answer = ""
        while True:
            try:
                event = await loop.run_in_executor(None, lambda: token_queue.get(timeout=120))
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] == "token":
                    full_answer += event["content"]
                elif event["type"] in ("done", "error"):
                    if event["type"] == "done":
                        full_answer = event.get("answer", full_answer)
                    break
            except sync_queue.Empty:
                yield f"data: {json.dumps({'type':'keepalive'})}\n\n"

        if full_answer:
            ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            get_conversations_col().update_one(
                {"session_id": body.session_id},
                {"$push": {"messages": {"timestamp": ts2, "role": "coach", "message": full_answer}},
                 "$inc": {"total_messages": 1}, "$set": {"last_updated": ts2}},
            )
            _user_histories[uid].extend([HumanMessage(content=body.message), AIMessage(content=full_answer)])
            if len(_user_histories[uid]) > 20:
                _user_histories[uid] = _user_histories[uid][-20:]

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
