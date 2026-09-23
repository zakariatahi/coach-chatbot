"""
db.py — MongoDB connection singleton for Personal Assistant (COACH).

Reads connection settings from .env:
  MONGO_URI  = mongodb://localhost:27017
  DB_NAME    = personal_assistant_db
  USER_ID    = default_user   (overridable via --user CLI flag)

User identity model
-------------------
  username  : human-readable login handle (unique, passed via --user)
  user_id   : UUID generated once at account creation (stable forever)

Two users named "Zakaria" can coexist as "zakaria" and "zakaria2" — their
UUIDs are completely separate, so their profiles and histories never mix.
"""

import os
import uuid as _uuid
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from dotenv import load_dotenv

load_dotenv()

_MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
_DB_NAME: str   = os.getenv("DB_NAME",   "personal_assistant_db")

# Single client instance reused for the lifetime of the process
_client: MongoClient | None = None


# ─────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────

def _ensure_indexes(client: MongoClient) -> None:
    """
    Create indexes on first connection (idempotent — safe every startup).

    users
      • user_id  — unique        : primary key, UUID, never changes
      • username — unique sparse : login handle, human-readable

    conversations
      • user_id   — regular      : fetch all sessions for a user  O(log n)
      • session_id — unique      : fast per-session read/write     O(log n)
    """
    db = client[_DB_NAME]

    db["users"].create_index(
        [("user_id", ASCENDING)],
        unique=True,
        name="idx_users_user_id",
    )
    db["users"].create_index(
        [("username", ASCENDING)],
        unique=True,
        sparse=True,          # allow legacy docs without a username field
        name="idx_users_username",
    )

    db["conversations"].create_index(
        [("user_id", ASCENDING)],
        name="idx_conversations_user_id",
    )
    db["conversations"].create_index(
        [("session_id", ASCENDING)],
        unique=True,
        name="idx_conversations_session_id",
    )


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(_MONGO_URI, serverSelectionTimeoutMS=5000)
        _client.server_info()          # fail fast if DB is unreachable
        _ensure_indexes(_client)
    return _client


# ─────────────────────────────────────────
# Public collection helpers
# ─────────────────────────────────────────

def get_db():
    """Returns the database instance."""
    return _get_client()[_DB_NAME]


def get_users_col() -> Collection:
    """Returns the 'users' collection."""
    return _get_client()[_DB_NAME]["users"]


def get_conversations_col() -> Collection:
    """Returns the 'conversations' collection."""
    return _get_client()[_DB_NAME]["conversations"]


# ─────────────────────────────────────────
# User identity helpers
# ─────────────────────────────────────────

def find_or_create_user(username: str) -> str:
    """
    Look up a user by their username.
    • Found  → return their stable UUID user_id.
    • Missing → create a new document with a fresh UUID and return it.

    This means two people who both call themselves "zakaria" must pick
    distinct usernames (e.g. "zakaria" and "zakaria2").  The UUID is what
    actually isolates their data — the username is just the login handle.
    """
    col = get_users_col()
    doc = col.find_one({"username": username}, {"user_id": 1})
    if doc:
        return doc["user_id"]

    # First time this username is seen → create the account
    user_id = str(_uuid.uuid4())
    col.insert_one({
        "user_id":    user_id,
        "username":   username,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[OK] New account created for '{username}' (id: {user_id[:8]}…)")
    return user_id


# ─────────────────────────────────────────
# History helpers
# ─────────────────────────────────────────

def get_user_history(user_id: str) -> list[dict]:
    """
    Return ALL conversation sessions for a user, oldest first.
    Each dict contains: session_id, date, started_at, total_messages, messages[].
    """
    col = get_conversations_col()
    return list(
        col.find(
            {"user_id": user_id},
            {"_id": 0, "session_id": 1, "date": 1,
             "started_at": 1, "total_messages": 1, "messages": 1},
        ).sort("started_at", ASCENDING)
    )


# ─────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────

def close():
    """Close the MongoDB connection (call on app shutdown if needed)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
