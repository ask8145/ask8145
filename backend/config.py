"""Settings and safety constants.

Secrets come ONLY from environment variables / a local .env file. They are
never logged, returned by the API, or written to disk by this program.
"""
from __future__ import annotations
import os
from pathlib import Path

# HARD-CODED safety switch. Phase 3 contains NO order-placement code for the
# broker, so this is False and nothing reads an env var to change it.
# Live trading will be added in a later phase only after your explicit approval.
LIVE_ORDERS_ENABLED = False

CACHE_DIR = Path(os.environ.get("AOT_CACHE_DIR", "cache"))
SCRIP_MASTER_URL = ("https://margincalculator.angelbroking.com/"
                    "OpenAPI_File/files/OpenAPIScripMaster.json")

# Index underlyings -> (index spot exchange, option exchange segment, spot symbol, spot token)
# Spot tokens are verified at runtime from the instrument master (AMXIDX rows);
# the values here are only name-matching hints, never trusted for orders.
UNDERLYINGS = {
    "NIFTY":      {"spot_exch": "NSE", "opt_exch": "NFO", "spot_name": "Nifty 50"},
    "BANKNIFTY":  {"spot_exch": "NSE", "opt_exch": "NFO", "spot_name": "Nifty Bank"},
    "FINNIFTY":   {"spot_exch": "NSE", "opt_exch": "NFO", "spot_name": "Nifty Fin Service"},
    "MIDCPNIFTY": {"spot_exch": "NSE", "opt_exch": "NFO", "spot_name": "NIFTY MID SELECT"},
    "SENSEX":     {"spot_exch": "BSE", "opt_exch": "BFO", "spot_name": "SENSEX"},
    "BANKEX":     {"spot_exch": "BSE", "opt_exch": "BFO", "spot_name": "BANKEX"},
}

def load_dotenv(path: str = ".env") -> None:
    """Tiny .env reader (no extra dependency). Does not override real env vars."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def credentials_present() -> dict[str, bool]:
    """Reports ONLY whether each secret is set — never the value."""
    return {k: bool(os.environ.get(k)) for k in
            ("ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PIN", "ANGEL_TOTP_SECRET")}
