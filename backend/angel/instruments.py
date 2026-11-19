"""Angel One instrument master (scrip master): download, cache, parse, query.

Lot sizes, expiries, strikes and tokens are READ from this file — never
hard-coded — because exchanges revise lot sizes and expiry days.
"""
from __future__ import annotations
import json, time
from datetime import datetime, date
from pathlib import Path
from typing import Optional
import pandas as pd
import requests
from .. import config

MAX_AGE_SECONDS = 12 * 3600

def _cache_path() -> Path:
    return config.CACHE_DIR / "scrip_master.json"

def download_master(force: bool = False, session=None) -> list[dict]:
    """Download (or reuse cached copy younger than 12h) the public scrip master."""
    p = _cache_path()
    if not force and p.exists() and time.time() - p.stat().st_mtime < MAX_AGE_SECONDS:
        return json.loads(p.read_text(encoding="utf-8"))
    r = (session or requests).get(config.SCRIP_MASTER_URL, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Scrip master response was empty or malformed.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    return data

def parse_expiry(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s.strip().upper(), "%d%b%Y").date()
    except (ValueError, AttributeError):
        return None

class InstrumentMaster:
    def __init__(self, rows: list[dict]):
        df = pd.DataFrame(rows)
        need = {"token", "symbol", "name", "expiry", "strike", "lotsize", "instrumenttype", "exch_seg"}
        missing = need - set(df.columns)
        if missing:
            raise ValueError("Scrip master missing columns: " + ", ".join(sorted(missing)))
        df["expiry_date"] = df["expiry"].map(parse_expiry)
        # Angel stores strike multiplied by 100
        df["strike_price"] = pd.to_numeric(df["strike"], errors="coerce") / 100.0
        df["lotsize"] = pd.to_numeric(df["lotsize"], errors="coerce")
        self.df = df

    @classmethod
    def load(cls, force: bool = False) -> "InstrumentMaster":
        return cls(download_master(force))

    def options(self, underlying: str) -> pd.DataFrame:
        info = config.UNDERLYINGS.get(underlying.upper())
        if not info:
            raise ValueError(f"Unsupported underlying: {underlying}")
        d = self.df
        d = d[(d.exch_seg == info["opt_exch"]) & (d.instrumenttype == "OPTIDX")
              & (d.name.str.upper() == underlying.upper())]
        return d.dropna(subset=["expiry_date", "strike_price"])

    def expiries(self, underlying: str, today: Optional[date] = None) -> list[date]:
        today = today or date.today()
        d = self.options(underlying)
        return sorted({e for e in d.expiry_date if e >= today})

    def lot_size(self, underlying: str, expiry: Optional[date] = None) -> Optional[int]:
        d = self.options(underlying)
        if expiry:
            d = d[d.expiry_date == expiry]
        sizes = d.lotsize.dropna().unique()
        if len(sizes) == 0:
            return None
        if len(sizes) > 1:
            raise ValueError(f"Conflicting lot sizes for {underlying}: {sorted(sizes)}")
        return int(sizes[0])

    def spot_instrument(self, underlying: str) -> Optional[dict]:
        """Index spot row (used for candle data). Matched by name, verified by exchange."""
        info = config.UNDERLYINGS[underlying.upper()]
        d = self.df
        d = d[(d.exch_seg == info["spot_exch"]) & (d.instrumenttype == "AMXIDX")
              & (d.name.str.upper() == info["spot_name"].upper())]
        return None if d.empty else d.iloc[0][["token", "symbol", "name", "exch_seg"]].to_dict()

    def chain_contracts(self, underlying: str, expiry: date, spot: float, strikes_each_side: int = 10) -> pd.DataFrame:
        """Option contracts for the strikes nearest to spot (ATM +/- N strikes)."""
        d = self.options(underlying)
        d = d[d.expiry_date == expiry]
        if d.empty:
            return d
        strikes = sorted(d.strike_price.unique())
        atm_i = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
        keep = set(strikes[max(0, atm_i - strikes_each_side): atm_i + strikes_each_side + 1])
        d = d[d.strike_price.isin(keep)].copy()
        d["option_type"] = d.symbol.str[-2:]
        return d[d.option_type.isin(["CE", "PE"])].sort_values(["strike_price", "option_type"])
