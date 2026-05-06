import threading
import time
from collections import defaultdict, deque

from config import LOGIN_BRUTEFORCE_BLOCK_SECONDS, LOGIN_BRUTEFORCE_MAX_ATTEMPTS


class LoginProtectionService:
    def __init__(self):
        self._attempts = defaultdict(deque)
        self._blocked_until = {}
        self._lock = threading.Lock()

    def _prune(self, key, now):
        window_start = now - LOGIN_BRUTEFORCE_BLOCK_SECONDS
        attempts = self._attempts[key]
        while attempts and attempts[0] < window_start:
            attempts.popleft()
        if not attempts:
            self._attempts.pop(key, None)

    def check_blocked_seconds(self, key):
        now = time.time()
        with self._lock:
            blocked_until = self._blocked_until.get(key)
            if blocked_until is None:
                return 0
            if blocked_until <= now:
                self._blocked_until.pop(key, None)
                return 0
            return int(blocked_until - now)

    def register_failure(self, key):
        now = time.time()
        with self._lock:
            self._prune(key, now)
            attempts = self._attempts[key]
            attempts.append(now)
            if len(attempts) >= LOGIN_BRUTEFORCE_MAX_ATTEMPTS:
                blocked_until = now + LOGIN_BRUTEFORCE_BLOCK_SECONDS
                self._blocked_until[key] = blocked_until
                self._attempts.pop(key, None)
                return int(blocked_until - now)
            return 0

    def register_success(self, key):
        with self._lock:
            self._attempts.pop(key, None)
            self._blocked_until.pop(key, None)


def login_key(email, client_ip):
    normalized_email = (email or "").strip().lower()
    return f"{normalized_email}:{client_ip or 'unknown'}"


login_protection_service = LoginProtectionService()
