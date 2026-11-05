"""Accounts and sign-in sessions, stored in data/accounts.json.

Passwords are stored as salted PBKDF2 hashes, and session tokens as SHA-256 hashes,
so the file never contains a password or a usable token.
"""

import hashlib
import hmac
import json
import re
import secrets
import time

from storage import DATA_DIR

ACCOUNTS_FILE = DATA_DIR / "accounts.json"
SESSION_DAYS = 30
_ITERATIONS = 200_000


def _load():
    if not ACCOUNTS_FILE.exists():
        return {"users": {}, "sessions": {}}
    return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))


def _save(data):
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _public(user):
    return {"id": user["id"], "name": user["name"], "email": user["email"]}


def create_user(name, email, password):
    """Create an account. Raises ValueError with a friendly message if something is wrong."""
    name, email = name.strip(), email.strip().lower()
    if not name:
        raise ValueError("Please tell us your name.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Please enter a valid email address.")
    if len(password) < 8:
        raise ValueError("Please use at least 8 characters for your password.")
    data = _load()
    if any(u["email"] == email for u in data["users"].values()):
        raise ValueError("An account with this email already exists. Try signing in.")
    salt = secrets.token_hex(16)
    user = {"id": "u_" + secrets.token_hex(6), "name": name, "email": email, "salt": salt,
            "password": _hash_password(password, salt), "created": time.time()}
    data["users"][user["id"]] = user
    _save(data)
    return _public(user)


def is_first_user(user_id):
    return list(_load()["users"]) == [user_id]


def authenticate(email, password):
    """The account for this email and password, or None."""
    email = email.strip().lower()
    for user in _load()["users"].values():
        if user["email"] == email and hmac.compare_digest(user["password"], _hash_password(password, user["salt"])):
            return _public(user)
    return None


def start_session(user_id):
    """Create a sign-in session and return its token (kept in a browser cookie)."""
    token = secrets.token_urlsafe(32)
    data = _load()
    now = time.time()
    data["sessions"] = {k: s for k, s in data["sessions"].items() if s["expires"] > now}  # drop expired
    data["sessions"][_hash_token(token)] = {"user": user_id, "expires": now + SESSION_DAYS * 86400}
    _save(data)
    return token


def user_for_session(token):
    if not isinstance(token, str) or not token:
        return None
    data = _load()
    session = data["sessions"].get(_hash_token(token))
    if not session or session["expires"] < time.time() or session["user"] not in data["users"]:
        return None
    return _public(data["users"][session["user"]])


def end_session(token):
    if not token:
        return
    data = _load()
    if data["sessions"].pop(_hash_token(token), None):
        _save(data)
