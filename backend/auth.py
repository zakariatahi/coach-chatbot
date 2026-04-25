"""Google OAuth + PKCE + JWT auth helpers."""

import os, sys, hashlib, secrets, base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests as http_req
from google_auth_oauthlib.flow import Flow
from jose import jwt, JWTError
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_db

load_dotenv()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
SECRET_KEY    = os.getenv("SECRET_KEY", "change-me")
ALGORITHM     = "HS256"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


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
    verifier  = secrets.token_urlsafe(96)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _save_pkce(state: str, verifier: str):
    get_db()["oauth_pkce"].replace_one(
        {"state": state},
        {"state": state, "code_verifier": verifier, "created_at": datetime.now()},
        upsert=True,
    )


def _pop_pkce(state: str) -> str:
    doc = get_db()["oauth_pkce"].find_one_and_delete({"state": state})
    return doc["code_verifier"] if doc else ""


def get_google_auth_url() -> str:
    verifier, challenge = _pkce_pair()
    flow = _make_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        prompt="select_account",
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    _save_pkce(state, verifier)
    return url


async def handle_oauth_callback(code: str, state: str) -> dict | None:
    verifier = _pop_pkce(state)
    if not verifier:
        return None
    try:
        flow = _make_flow()
        auth_response = f"{REDIRECT_URI}?code={code}&state={state}"
        flow.fetch_token(authorization_response=auth_response, code_verifier=verifier)
        creds = flow.credentials
        resp = http_req.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=8,
        )
        info = resp.json()
        return info if "email" in info else None
    except Exception as e:
        print(f"OAuth error: {e}")
        return None


def create_jwt(data: dict) -> str:
    payload = {**data, "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
