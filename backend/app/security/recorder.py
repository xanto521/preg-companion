from collections import OrderedDict
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

from argon2 import PasswordHasher

SESSION_COOKIE = "preg_recorder"
SESSION_TTL = timedelta(hours=12)
SETUP_TTL = timedelta(hours=1)
password_hasher = PasswordHasher()


def new_token() -> str:
    return token_urlsafe(32)


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class LoginLimiter:
    window = 300
    max_attempts = 8

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: OrderedDict[str, tuple[float, int]] = OrderedDict()

    def allow(self, client: str) -> bool:
        now = monotonic()
        with self._lock:
            while self._entries:
                first, (expires, _) = next(iter(self._entries.items()))
                if expires > now:
                    break
                del self._entries[first]
            expires, attempts = self._entries.get(client, (now + self.window, 0))
            if attempts >= self.max_attempts:
                return False
            if len(self._entries) >= 4096 and client not in self._entries:
                self._entries.popitem(last=False)
            self._entries[client] = (expires, attempts + 1)
            return True
