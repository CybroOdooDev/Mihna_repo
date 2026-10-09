"""Signed, expiring candidate tokens and a small in-process rate limiter."""
import base64
import hashlib
import hmac
import secrets
import threading
import time


def make_token(secret, session_id, expires_at):
    """Return ``<nonce>.<sig>``; the signature binds session id + expiry, verified server-side."""
    nonce = secrets.token_urlsafe(18)
    return f"{nonce}.{_sign(secret, nonce, session_id, expires_at)}"


def _sign(secret, nonce, session_id, expires_at):
    msg = f"{nonce}:{session_id}:{int(expires_at)}".encode()
    digest = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest)[:32].decode()


def verify_signature(secret, token, session_id, expires_at):
    try:
        nonce, sig = token.split(".", 1)
    except (AttributeError, ValueError):
        return False
    return hmac.compare_digest(sig, _sign(secret, nonce, session_id, expires_at))


def verify_token(secret, token, session_id, expires_at):
    return verify_signature(secret, token, session_id, expires_at) and time.time() <= expires_at


class RateLimiter:
    """Sliding-window limiter keyed by (ip, bucket). Per worker process, which is enough to blunt abuse."""

    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key, limit, window=60):
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window]
            if len(hits) >= limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            if len(self._hits) > 10000:
                self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < window}
            return True


limiter = RateLimiter()
