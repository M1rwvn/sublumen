"""M08 auth: Argon2id password hashes, signed expiring tokens, roles, in-memory rate limiter."""
import time, threading
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_ph = PasswordHasher()

def hash_password(pw: str) -> str:
    if len(pw) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return _ph.hash(pw)

def verify_password(h: str, pw: str) -> bool:
    try:
        return _ph.verify(h, pw)
    except (VerifyMismatchError, InvalidHashError):
        return False

class Tokens:
    def __init__(self, secret, ttl): self.s = URLSafeTimedSerializer(secret, salt="ss-auth"); self.ttl = ttl
    def issue(self, uid, role): return self.s.dumps({"uid": uid, "role": role})
    def load(self, tok):
        try: return self.s.loads(tok, max_age=self.ttl)
        except (BadSignature, SignatureExpired): return None

class RateLimiter:
    def __init__(self): self.hits, self.lock = {}, threading.Lock()
    def allow(self, key, limit, window=60):
        t = time.time()
        with self.lock:
            q = [x for x in self.hits.get(key, []) if t - x < window]
            if len(q) >= limit:
                self.hits[key] = q; return False
            q.append(t); self.hits[key] = q; return True
