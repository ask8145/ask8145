"""Angel One SmartAPI login/session handling (read-only features only).

SECURITY: secrets are read from environment variables, kept only in memory,
and are never logged, printed, or returned by any API route.
"""
from __future__ import annotations
import os, threading, time
from typing import Any, Callable, Optional

class AngelError(Exception):
    pass

def _redact(msg: str) -> str:
    """Strip any secret values from an error message before it can be shown."""
    for k in ("ANGEL_API_KEY", "ANGEL_PIN", "ANGEL_TOTP_SECRET", "ANGEL_CLIENT_CODE"):
        v = os.environ.get(k)
        if v:
            msg = msg.replace(v, "***")
    return msg

class AngelSession:
    """Wraps SmartConnect. `connect_factory` lets tests inject a fake client."""
    def __init__(self, connect_factory: Optional[Callable[[str], Any]] = None,
                 totp_func: Optional[Callable[[str], str]] = None):
        self._factory = connect_factory
        self._totp = totp_func
        self._client = None
        self._lock = threading.Lock()
        self.logged_in_at: Optional[float] = None
        self._last_call = 0.0

    # --- lifecycle -------------------------------------------------
    def login(self) -> dict:
        env = {k: os.environ.get(k, "") for k in
               ("ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PIN", "ANGEL_TOTP_SECRET")}
        missing = [k for k, v in env.items() if not v]
        if missing:
            raise AngelError("Missing settings in .env: " + ", ".join(missing))
        try:
            factory = self._factory or self._default_factory
            totp = self._totp or self._default_totp
            client = factory(env["ANGEL_API_KEY"])
            resp = client.generateSession(env["ANGEL_CLIENT_CODE"], env["ANGEL_PIN"], totp(env["ANGEL_TOTP_SECRET"]))
        except AngelError:
            raise
        except Exception as e:  # network, library, bad TOTP...
            raise AngelError("Login failed: " + _redact(str(e))) from None
        if not resp or not resp.get("status"):
            raise AngelError("Login rejected by Angel One: " + _redact(str((resp or {}).get("message", "unknown"))))
        with self._lock:
            self._client = client
            self.logged_in_at = time.time()
        return {"logged_in": True}

    def logout(self) -> None:
        with self._lock:
            c, self._client, self.logged_in_at = self._client, None, None
        if c is not None:
            try:
                c.terminateSession(os.environ.get("ANGEL_CLIENT_CODE", ""))
            except Exception:
                pass

    @property
    def is_logged_in(self) -> bool:
        return self._client is not None

    def client(self):
        if self._client is None:
            raise AngelError("Not logged in to Angel One. Call /angel/login first.")
        return self._client

    def throttled(self, min_interval: float = 0.4):
        """Simple rate limiter: keeps data requests at least `min_interval` s apart."""
        with self._lock:
            wait = self._last_call + min_interval - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
        return self.client()

    # --- defaults (real libraries, imported lazily) ----------------
    @staticmethod
    def _default_factory(api_key: str):
        try:
            from SmartApi import SmartConnect
        except ImportError:
            raise AngelError("Package 'smartapi-python' is not installed. Run: pip install smartapi-python") from None
        return SmartConnect(api_key=api_key)

    @staticmethod
    def _default_totp(secret: str) -> str:
        import pyotp
        return pyotp.TOTP(secret).now()
