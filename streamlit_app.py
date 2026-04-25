import os, uuid, io, hashlib, secrets, base64
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
import requests as http_req
from pymongo import DESCENDING
from google_auth_oauthlib.flow import Flow
from langchain_ollama import ChatOllama
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import HumanMessage, AIMessage
from db import get_conversations_col, get_db, find_or_create_user
from Coach import UserProfile, make_profile_tools, tools_list, build_prompt

load_dotenv()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# ── Config ─────────────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")
MODEL         = "gemma4:e2b"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# ── Page config (MUST be first Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title="COACH AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, html, body { font-family: 'Inter', sans-serif !important; box-sizing: border-box; }
.stApp { background: #0D0D0D; color: #E8E8E8; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #111118 !important; border-right: 1px solid #252540; }
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
.sidebar-logo { padding: 20px 16px 14px; border-bottom: 1px solid #252540; display:flex; align-items:center; gap:10px; }
.sidebar-logo .name { font-size:15px; font-weight:700; color:#E8E8E8; }
.sidebar-logo .sub  { font-size:11px; color:#555; }
.sidebar-section { padding: 10px 10px 4px; }
.session-btn { width:100%; text-align:left; background:transparent; border:none; color:#BBB;
  padding:9px 12px; border-radius:9px; font-size:13px; cursor:pointer; border-left:3px solid transparent;
  transition:all .18s; display:block; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.session-btn:hover { background:#1A1A2E; border-left-color:#6C63FF; color:#DDD; }
.session-btn.active { background:#1E1E30; border-left-color:#A78BFA; color:#E8E8E8; font-weight:600; }
.session-date { font-size:10px; color:#555; }
.user-card { position:fixed; bottom:0; left:0; width:280px; background:#111118;
  border-top:1px solid #252540; padding:12px 14px; display:flex; align-items:center; gap:10px; }
.user-card img { width:34px; height:34px; border-radius:50%; border:2px solid #6C63FF; }
.user-card .uname { font-size:13px; font-weight:600; color:#E8E8E8; }
.user-card .uemail { font-size:11px; color:#666; }

/* ── Chat messages ── */
.chat-wrap { padding: 24px 10% 100px; max-width:900px; margin:0 auto; }
.msg-row-user  { display:flex; justify-content:flex-end; margin:10px 0; }
.msg-row-coach { display:flex; justify-content:flex-start; margin:10px 0; gap:10px; align-items:flex-start; }
.bubble-user  { background:#1E2045; color:#D8D8FF; border-radius:18px 18px 4px 18px;
  padding:12px 18px; max-width:72%; line-height:1.65; font-size:14px; }
.bubble-coach { background:#13131F; border:1px solid #2A2A42; border-left:3px solid #6C63FF;
  color:#E0E0E8; border-radius:4px 18px 18px 18px; padding:12px 18px;
  max-width:72%; line-height:1.65; font-size:14px; }

.sidebar-logo {
  padding: 22px 18px 16px;
  border-bottom: 1px solid rgba(108,99,255,.15);
  display:flex; align-items:center; gap:12px;
  background: linear-gradient(135deg, rgba(108,99,255,.08), transparent);
}
.sidebar-logo .name {
  font-size:15px; font-weight:700;
  background: linear-gradient(135deg,#C4B5FD,#818CF8);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.sidebar-logo .sub { font-size:11px; color:#3A3A5A; margin-top:2px; }
.group-label {
  font-size:10px; font-weight:700; color:#30305A;
  letter-spacing:1px; text-transform:uppercase; padding:14px 16px 4px;
}

/* Session list buttons */
[data-testid="stSidebar"] .stButton > button {
  background: transparent !important; border: none !important;
  border-left: 3px solid transparent !important;
  border-radius: 0 10px 10px 0 !important;
  color: #6666AA !important; font-size: 13px !important;
  font-weight: 400 !important; padding: 9px 14px !important;
  text-align: left !important; width: 100% !important;
  transition: all .18s ease !important;
  box-shadow: none !important; transform: none !important;
  justify-content: flex-start !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(108,99,255,.1) !important;
  border-left-color: #6C63FF !important;
  color: #CCCCEE !important;
  transform: none !important; box-shadow: none !important;
}

/* New Chat override */
.new-chat-wrap .stButton > button {
  background: linear-gradient(135deg,#6C63FF,#A78BFA) !important;
  color: #fff !important; border-radius: 12px !important;
  border-left: none !important; font-weight: 600 !important;
  width: calc(100% - 24px) !important; margin: 10px 12px !important;
  box-shadow: 0 4px 20px rgba(108,99,255,.35) !important;
}
.new-chat-wrap .stButton > button:hover {
  box-shadow: 0 6px 28px rgba(108,99,255,.55) !important;
  transform: translateY(-1px) !important;
}

/* ── Chat bubbles ── */
.chat-wrap { padding: 28px 8% 130px; max-width: 860px; margin: 0 auto; }
.msg-row-user  { display:flex; justify-content:flex-end; margin:14px 0; align-items:flex-end; gap:10px; }
.msg-row-coach { display:flex; justify-content:flex-start; margin:14px 0; gap:12px; align-items:flex-start; }

.bubble-user {
  background: linear-gradient(135deg, #2A2060, #1E1A50);
  color: #D8D8FF; border-radius: 20px 20px 4px 20px;
  padding: 13px 18px; max-width: 70%; line-height: 1.7; font-size: 14px;
  box-shadow: 0 4px 20px rgba(108,99,255,.25);
}
.bubble-coach {
  background: rgba(18,18,32,.95); border: 1px solid rgba(108,99,255,.2);
  border-left: 3px solid #6C63FF; color: #D0D0E8;
  border-radius: 4px 20px 20px 20px; padding: 13px 18px;
  max-width: 70%; line-height: 1.7; font-size: 14px;
  box-shadow: 0 4px 24px rgba(0,0,0,.35); white-space: pre-wrap;
}
.coach-avatar {
  width:32px; height:32px; flex-shrink:0; margin-top:4px;
  background: linear-gradient(135deg,#6C63FF,#A78BFA);
  border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-size:15px; box-shadow:0 2px 14px rgba(108,99,255,.4);
}
.user-avatar-wrap {
  width:32px; height:32px; flex-shrink:0; border-radius:50%;
  overflow:hidden; border:2px solid rgba(108,99,255,.35); margin-top:4px;
}
.user-avatar-wrap img { width:100%; height:100%; object-fit:cover; }
.msg-meta { font-size:10px; color:#28284A; margin-top:5px; }
.msg-meta-r { text-align:right; }

/* ── Chat input ── */
[data-testid="stChatInput"] {
  background: rgba(8,8,16,.96) !important;
  border-top: 1px solid rgba(108,99,255,.15) !important;
  padding: 14px 8% !important; backdrop-filter: blur(14px);
}
[data-testid="stChatInput"] textarea {
  background: rgba(18,18,32,.9) !important; color: #E8E8F0 !important;
  border: 1px solid rgba(108,99,255,.3) !important;
  border-radius: 14px !important; font-size: 14px !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: rgba(108,99,255,.7) !important;
  box-shadow: 0 0 0 3px rgba(108,99,255,.1) !important;
}

/* ── Global buttons ── */
.stButton > button {
  background: linear-gradient(135deg,#6C63FF,#A78BFA) !important;
  color: #fff !important; border: none !important; border-radius: 12px !important;
  font-weight: 600 !important; font-size: 13px !important;
  transition: all .2s !important; padding: 9px 16px !important;
}
.stButton > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 24px rgba(108,99,255,.45) !important;
}
.logout-btn > button {
  background: transparent !important; color: #33334A !important;
  border: 1px solid #1E1E30 !important; font-size: 11px !important;
  padding: 5px 12px !important;
}
.logout-btn > button:hover {
  color: #FF7070 !important; border-color: rgba(255,112,112,.4) !important;
  box-shadow: none !important; transform: none !important;
}

/* ── Login page ── */
.login-outer {
  min-height:100vh; display:flex; align-items:center; justify-content:center;
  background: radial-gradient(ellipse 70% 60% at 50% 35%, rgba(108,99,255,.2) 0%,
    rgba(167,139,250,.07) 45%, #080810 72%);
}
.login-card {
  background: rgba(255,255,255,.038); backdrop-filter: blur(28px);
  border: 1px solid rgba(255,255,255,.08); border-radius: 28px;
  padding: 54px 50px; width: 430px; text-align: center;
  box-shadow: 0 32px 96px rgba(0,0,0,.7), inset 0 1px 0 rgba(255,255,255,.06);
}
.login-card h1 {
  background: linear-gradient(135deg,#E8E8FF,#A78BFA);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.google-btn {
  display:inline-flex; align-items:center; gap:12px;
  background:#fff; color:#1A1A1A; padding:13px 30px; border-radius:14px;
  font-size:15px; font-weight:600; text-decoration:none;
  box-shadow:0 4px 24px rgba(0,0,0,.5); transition:all .25s;
}
.google-btn:hover { transform:translateY(-3px); box-shadow:0 12px 36px rgba(0,0,0,.65); }

/* ── Upload zone ── */
.upload-zone {
  border:2px dashed rgba(108,99,255,.28); border-radius:22px;
  padding:56px 32px; text-align:center; margin:48px auto; max-width:500px;
  background:rgba(108,99,255,.04); transition:border-color .25s;
}
.upload-zone:hover { border-color:rgba(108,99,255,.55); }

/* ── Chat header ── */
.chat-header { padding:14px 10%; border-bottom:1px solid #1E1E30; background:#0D0D0D;
  font-size:15px; font-weight:600; color:#C0C0D8; position:sticky; top:0; z-index:10; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# OAuth helpers  (PKCE stored in MongoDB — survives cross-domain redirects)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_flow() -> Flow:
    return Flow.from_client_config(
        {"web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }},
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def _pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and its S256 code_challenge."""
    verifier  = secrets.token_urlsafe(96)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _save_pkce(state: str, code_verifier: str):
    """Persist (state → code_verifier) in MongoDB so it survives the redirect."""
    get_db()["oauth_pkce"].replace_one(
        {"state": state},
        {"state": state, "code_verifier": code_verifier, "created_at": datetime.now()},
        upsert=True,
    )


def _pop_pkce(state: str) -> str:
    """Retrieve and delete the code_verifier for a given state."""
    col = get_db()["oauth_pkce"]
    doc = col.find_one_and_delete({"state": state})
    return doc["code_verifier"] if doc else ""


def get_google_auth_url() -> str:
    verifier, challenge = _pkce_pair()
    flow = _make_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="select_account",
        include_granted_scopes="true",
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    _save_pkce(state, verifier)   # ← stored in MongoDB, not session_state
    return auth_url


def handle_oauth_callback(params: dict) -> bool:
    try:
        state         = params.get("state", "")
        code_verifier = _pop_pkce(state)   # ← retrieved from MongoDB
        if not code_verifier:
            st.error("OAuth state expired or not found. Please try signing in again.")
            return False

        flow = _make_flow()
        auth_response = REDIRECT_URI + "?" + "&".join(
            f"{k}={v}" for k, v in params.items()
        )
        flow.fetch_token(
            authorization_response=auth_response,
            code_verifier=code_verifier,
        )
        creds = flow.credentials
        resp  = http_req.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=8,
        )
        info = resp.json()
        if "email" not in info:
            st.error(f"Google did not return an email. Response: {info}")
            return False
        user_id = find_or_create_user(info["email"])
        st.session_state.authenticated = True
        st.session_state.user_info     = info
        st.session_state.user_id       = user_id
        return True
    except Exception as e:
        import traceback
        st.error(f"Authentication failed: {e}")
        st.code(traceback.format_exc(), language="text")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MongoDB session helpers
# ═══════════════════════════════════════════════════════════════════════════════

def create_session(user_id: str) -> str:
    sid = str(uuid.uuid4())[:8]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    get_conversations_col().insert_one({
        "session_id": sid, "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "started_at": now, "last_updated": now,
        "title": "New Chat", "messages": [], "total_messages": 0,
    })
    return sid


def append_message(sid: str, role: str, content: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    get_conversations_col().update_one(
        {"session_id": sid},
        {"$push": {"messages": {"timestamp": ts, "role": role, "message": content}},
         "$inc": {"total_messages": 1}, "$set": {"last_updated": ts}},
    )


def set_title(sid: str, title: str):
    get_conversations_col().update_one(
        {"session_id": sid}, {"$set": {"title": title[:55]}}
    )


def list_sessions(user_id: str) -> list:
    return list(
        get_conversations_col().find(
            {"user_id": user_id},
            {"session_id": 1, "title": 1, "date": 1, "total_messages": 1, "_id": 0},
        ).sort("last_updated", DESCENDING)
    )


def load_session_messages(sid: str) -> list:
    doc = get_conversations_col().find_one({"session_id": sid})
    return doc.get("messages", []) if doc else []


# ═══════════════════════════════════════════════════════════════════════════════
# File loader
# ═══════════════════════════════════════════════════════════════════════════════

def load_file(f) -> str:
    ext = f.name.lower().rsplit(".", 1)[-1]
    if ext == "txt":
        return f.read().decode("utf-8")
    if ext == "pdf":
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(f.read())).pages)
    raise ValueError("Only .txt and .pdf files are supported.")


# ═══════════════════════════════════════════════════════════════════════════════
# Agent builder
# ═══════════════════════════════════════════════════════════════════════════════

def get_executor() -> AgentExecutor:
    if "executor" not in st.session_state:
        profile = st.session_state.profile
        llm = ChatOllama(
            model=MODEL, streaming=False,
            num_ctx=2048, num_thread=max(1, os.cpu_count() - 1),
        )
        all_tools = tools_list + make_profile_tools(profile)
        prompt = build_prompt(st.session_state.log_content)
        agent = create_tool_calling_agent(llm, all_tools, prompt)
        st.session_state.executor = AgentExecutor(
            agent=agent, tools=all_tools, verbose=False, max_iterations=6
        )
    return st.session_state.executor


# ═══════════════════════════════════════════════════════════════════════════════
# State helpers
# ═══════════════════════════════════════════════════════════════════════════════

def start_new_session():
    sid = create_session(st.session_state.user_id)
    st.session_state.current_session_id = sid
    st.session_state.messages = []
    st.session_state.chat_history = []
    for k in ("executor",):
        st.session_state.pop(k, None)


def switch_session(sid: str):
    st.session_state.current_session_id = sid
    st.session_state.messages = load_session_messages(sid)
    st.session_state.chat_history = []
    st.session_state.pop("executor", None)


def do_logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


# ═══════════════════════════════════════════════════════════════════════════════
# Login page
# ═══════════════════════════════════════════════════════════════════════════════

def render_login():
    auth_url = get_google_auth_url()
    st.markdown(f"""
    <div class="login-outer">
      <div class="login-card">
        <div style="font-size:52px;margin-bottom:12px;">🧠</div>
        <h1 style="font-size:26px;font-weight:700;color:#E8E8E8;margin:0 0 6px;">COACH AI</h1>
        <p style="color:#666;font-size:13px;margin-bottom:36px;line-height:1.6;">
          Your personal AI coach for productivity,<br>wellness, and daily planning.
        </p>
        <a href="{auth_url}" class="google-btn">
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Sign in with Google
        </a>
        <p style="color:#444;font-size:11px;margin-top:28px;">
          Secured with Google OAuth 2.0 · Your data stays private
        </p>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    from datetime import date as _date, timedelta
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-logo">
          <span style="font-size:28px;">🧠</span>
          <div><div class="name">COACH AI</div><div class="sub">Personal Productivity Coach</div></div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="new-chat-wrap">', unsafe_allow_html=True)
        if st.button("＋  New Chat", use_container_width=True, key="new_chat"):
            start_new_session()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Grouped sessions ──────────────────────────────────────────────────
        sessions = list_sessions(st.session_state.user_id)
        current  = st.session_state.get("current_session_id", "")
        today     = _date.today()
        yesterday = today - timedelta(days=1)
        week_ago  = today - timedelta(days=7)

        groups = {"Today": [], "Yesterday": [], "This week": [], "Earlier": []}
        for s in sessions:
            try:
                d = _date.fromisoformat(s.get("date", str(today)))
            except Exception:
                d = today
            if d == today:          groups["Today"].append(s)
            elif d == yesterday:    groups["Yesterday"].append(s)
            elif d >= week_ago:     groups["This week"].append(s)
            else:                   groups["Earlier"].append(s)

        if not sessions:
            st.markdown('<p style="color:#2A2A4A;font-size:12px;text-align:center;padding:28px 10px;">No conversations yet.<br>Start a new chat!</p>', unsafe_allow_html=True)

        for group, items in groups.items():
            if not items:
                continue
            st.markdown(f'<div class="group-label">{group}</div>', unsafe_allow_html=True)
            for s in items:
                sid   = s["session_id"]
                title = s.get("title", "New Chat")
                count = s.get("total_messages", 0)
                icon  = "💬" if sid == current else "·"
                label = f"{icon}  {title}"
                if st.button(label, key=f"s_{sid}", use_container_width=True,
                             help=f"{s.get('date','')} · {count} messages"):
                    switch_session(sid)
                    st.rerun()

        # ── User card ─────────────────────────────────────────────────────────
        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
        st.divider()
        user  = st.session_state.user_info
        pic   = user.get("picture", "")
        name  = user.get("name", "User")
        email = user.get("email", "")
        col1, col2 = st.columns([1, 3])
        with col1:
            if pic:
                st.image(pic, width=36)
            else:
                st.markdown(f'<div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#6C63FF,#A78BFA);display:flex;align-items:center;justify-content:center;font-size:16px;color:white;">{name[0].upper()}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div style="font-size:13px;font-weight:600;color:#CCCCDD;">{name}</div><div style="font-size:10px;color:#44445A;">{email}</div>', unsafe_allow_html=True)
        st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
        if st.button("Sign out", key="logout", use_container_width=True):
            do_logout(); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Chat page
# ═══════════════════════════════════════════════════════════════════════════════

def render_chat():
    user_info  = st.session_state.user_info
    user_pic   = user_info.get("picture", "")
    user_name  = user_info.get("name", "You")
    has_log    = "log_content" in st.session_state
    has_session = "current_session_id" in st.session_state

    # ── If viewing a past session (no log), show it read-only ─────────────────
    if has_session and not has_log:
        msgs = st.session_state.get("messages", [])
        doc  = get_conversations_col().find_one(
            {"session_id": st.session_state.current_session_id}, {"title": 1, "date": 1}
        )
        title    = doc.get("title", "Session") if doc else "Session"
        date_str = doc.get("date", "")         if doc else ""

        st.markdown(f"""
        <div class="chat-header">
          💬 {title}
          <span class="history-badge">📅 {date_str}</span>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
        if not msgs:
            st.markdown('<div style="text-align:center;padding:60px;color:#33334A;">This session has no messages.</div>', unsafe_allow_html=True)
        for m in msgs:
            role = m["role"]; text = m["message"]; ts = m.get("timestamp", "")[-8:-3]
            if role == "human":
                avatar_html = f'<div class="user-avatar-wrap"><img src="{user_pic}"/></div>' if user_pic else f'<div class="coach-avatar" style="background:#2A2060;font-size:13px;">{user_name[0].upper()}</div>'
                st.markdown(f'<div class="msg-row-user"><div><div class="bubble-user">{text}</div><div class="msg-meta msg-meta-r">{ts}</div></div>{avatar_html}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="msg-row-coach"><div class="coach-avatar">🧠</div><div><div class="bubble-coach">{text}</div><div class="msg-meta">COACH · {ts}</div></div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Offer to continue this session by uploading a log
        st.markdown('<div style="border-top:1px solid rgba(108,99,255,.12);padding:16px 8%;text-align:center;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px;color:#44446A;margin-bottom:10px;">📂 Upload a log file to continue this conversation</div>', unsafe_allow_html=True)
        up = st.file_uploader("", type=["txt", "pdf"], label_visibility="collapsed", key="hist_uploader")
        if up:
            with st.spinner("Loading log…"):
                st.session_state.log_content  = load_file(up)
                st.session_state.log_filename = up.name
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── No session and no log → show upload gate ──────────────────────────────
    if not has_log:
        st.markdown("""
        <div style="display:flex;align-items:center;justify-content:center;min-height:80vh;">
          <div class="upload-zone">
            <div style="font-size:48px;margin-bottom:16px;">📂</div>
            <div style="font-size:20px;font-weight:700;color:#CCCCDD;margin-bottom:8px;">Upload Your Daily Log</div>
            <div style="font-size:13px;color:#44446A;margin-bottom:24px;line-height:1.7;">
              Share a <strong>.txt</strong> or <strong>.pdf</strong> file to start<br>your personal coaching session.
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
        up = st.file_uploader("", type=["txt", "pdf"], label_visibility="collapsed", key="log_uploader")
        if up:
            with st.spinner("Loading log file…"):
                st.session_state.log_content  = load_file(up)
                st.session_state.log_filename = up.name
            st.rerun()
        return

    # ── Active chat ───────────────────────────────────────────────────────────
    if not has_session:
        start_new_session()
    if "profile" not in st.session_state:
        st.session_state.profile = UserProfile(user_id=st.session_state.user_id)
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    msgs        = st.session_state.get("messages", [])
    current_sid = st.session_state.current_session_id
    doc         = get_conversations_col().find_one({"session_id": current_sid}, {"title": 1})
    title       = doc.get("title", "New Chat") if doc else "New Chat"
    file_lbl    = st.session_state.get("log_filename", "log file")

    st.markdown(f"""
    <div class="chat-header">
      💬 {title}
      <span style="font-size:11px;color:#33334A;font-weight:400;">📂 {file_lbl}</span>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    if not msgs:
        st.markdown(f"""
        <div style="text-align:center;padding:80px 0 40px;">
          <div style="font-size:48px;margin-bottom:18px;">👋</div>
          <div style="font-size:20px;font-weight:700;color:#8888AA;">Hello, {user_name.split()[0]}!</div>
          <div style="font-size:13px;color:#33334A;margin-top:10px;line-height:1.8;">
            Ask me anything about your productivity,<br>sleep, goals, or today's plan.
          </div>
        </div>""", unsafe_allow_html=True)

    for m in msgs:
        role = m["role"]; text = m["message"]; ts = m.get("timestamp", "")[-8:-3]
        if role == "human":
            avatar_html = f'<div class="user-avatar-wrap"><img src="{user_pic}"/></div>' if user_pic else f'<div class="coach-avatar" style="background:#2A2060;font-size:13px;">{user_name[0].upper()}</div>'
            st.markdown(f'<div class="msg-row-user"><div><div class="bubble-user">{text}</div><div class="msg-meta msg-meta-r">{ts}</div></div>{avatar_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="msg-row-coach"><div class="coach-avatar">🧠</div><div><div class="bubble-coach">{text}</div><div class="msg-meta">COACH · {ts}</div></div></div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    user_input = st.chat_input("Ask your coach anything…")
    if user_input:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.messages.append({"role": "human", "message": user_input, "timestamp": ts})
        append_message(current_sid, "human", user_input)
        if len(st.session_state.messages) == 1:
            set_title(current_sid, user_input)
        with st.spinner("🧠 COACH is thinking…"):
            try:
                resp   = get_executor().invoke({"input": user_input, "chat_history": st.session_state.chat_history, "user_profile": st.session_state.profile.to_prompt_string()})
                answer = resp["output"]
            except Exception as e:
                answer = f"⚠️ Something went wrong: {e}"
        ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.messages.append({"role": "coach", "message": answer, "timestamp": ts2})
        append_message(current_sid, "coach", answer)
        st.session_state.chat_history.extend([HumanMessage(content=user_input), AIMessage(content=answer)])
        if len(st.session_state.chat_history) > 20:
            st.session_state.chat_history = st.session_state.chat_history[-20:]
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    params = st.query_params

    # Handle OAuth callback
    if "code" in params and not st.session_state.get("authenticated"):
        with st.spinner("Signing you in…"):
            ok = handle_oauth_callback(dict(params))
        st.query_params.clear()
        if ok:
            st.rerun()
        return

    # Not authenticated → login page
    if not st.session_state.get("authenticated"):
        render_login()
        return

    # Authenticated → full app
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
