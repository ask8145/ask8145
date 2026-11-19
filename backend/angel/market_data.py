"""Read-only market data: historical candles, LTP, option-chain snapshot.

No function in this module can place, modify or cancel an order.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Optional
import pandas as pd
from .instruments import InstrumentMaster
from .session import AngelSession, AngelError

# Angel One's documented per-request maximum look-back (days) by interval.
MAX_DAYS = {"ONE_MINUTE": 30, "THREE_MINUTE": 60, "FIVE_MINUTE": 100, "TEN_MINUTE": 100,
            "FIFTEEN_MINUTE": 200, "THIRTY_MINUTE": 200, "ONE_HOUR": 400, "ONE_DAY": 2000}
CHUNK_FALLBACK = 25

def fetch_candles(sess: AngelSession, exchange: str, token: str, symbol: str,
                  interval: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Historical candles in the same schema as the Phase 1/2 OHLCV CSV."""
    if interval not in MAX_DAYS:
        raise ValueError(f"Unsupported interval {interval}. Use one of {sorted(MAX_DAYS)}")
    if start >= end:
        raise ValueError("start must be before end")
    span = timedelta(days=MAX_DAYS[interval])
    rows, cur = [], start
    while cur < end:
        nxt = min(cur + span, end)
        resp = sess.throttled().getCandleData({
            "exchange": exchange, "symboltoken": str(token), "interval": interval,
            "fromdate": cur.strftime("%Y-%m-%d %H:%M"), "todate": nxt.strftime("%Y-%m-%d %H:%M")})
        if not resp or not resp.get("status"):
            raise AngelError("Candle request failed: " + str((resp or {}).get("message", "unknown")))
        rows.extend(resp.get("data") or [])
        cur = nxt
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    if df.empty:
        return df.assign(symbol=symbol)[["timestamp", "symbol", "open", "high", "low", "close", "volume"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df["symbol"] = symbol
    return df[["timestamp", "symbol", "open", "high", "low", "close", "volume"]].reset_index(drop=True)

def _market_data(sess: AngelSession, mode: str, exch_tokens: dict[str, list[str]]) -> list[dict]:
    resp = sess.throttled().getMarketData(mode, exch_tokens)
    if not resp or not resp.get("status"):
        raise AngelError("Market data request failed: " + str((resp or {}).get("message", "unknown")))
    return (resp.get("data") or {}).get("fetched", [])

def spot_ltp(sess: AngelSession, master: InstrumentMaster, underlying: str) -> float:
    spot = master.spot_instrument(underlying)
    if not spot:
        raise AngelError(f"Spot instrument for {underlying} not found in instrument master.")
    got = _market_data(sess, "LTP", {spot["exch_seg"]: [str(spot["token"])]})
    if not got:
        raise AngelError("No spot price returned.")
    return float(got[0]["ltp"])

def option_chain_snapshot(sess: AngelSession, master: InstrumentMaster, underlying: str,
                          expiry: Optional[date] = None, strikes_each_side: int = 10,
                          now: Optional[datetime] = None) -> pd.DataFrame:
    """Live chain snapshot in the Phase 2 chain schema
    (timestamp, underlying, expiry, strike, option_type, ltp, bid, ask, volume, oi)
    plus lot_size and tradingsymbol. Batches requests (API max 50 tokens/request)."""
    now = now or datetime.now()
    if expiry is None:
        exps = master.expiries(underlying, now.date())
        if not exps:
            raise AngelError(f"No upcoming expiries found for {underlying}.")
        expiry = exps[0]
    spot = spot_ltp(sess, master, underlying)
    contracts = master.chain_contracts(underlying, expiry, spot, strikes_each_side)
    if contracts.empty:
        raise AngelError(f"No contracts for {underlying} {expiry}.")
    exch = contracts.exch_seg.iloc[0]
    tokens = [str(t) for t in contracts.token]
    quotes: dict[str, dict] = {}
    for i in range(0, len(tokens), 50):
        for q in _market_data(sess, "FULL", {exch: tokens[i:i + 50]}):
            quotes[str(q.get("symbolToken"))] = q
    out = []
    for _, c in contracts.iterrows():
        q = quotes.get(str(c.token))
        if not q:
            continue  # no quote -> skip rather than invent a price
        depth = q.get("depth") or {}
        bids, asks = depth.get("buy") or [], depth.get("sell") or []
        out.append({"timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "underlying": underlying.upper(),
                    "expiry": expiry.isoformat(), "strike": float(c.strike_price), "option_type": c.option_type,
                    "ltp": float(q.get("ltp", 0)),
                    "bid": float(bids[0]["price"]) if bids else 0.0,
                    "ask": float(asks[0]["price"]) if asks else 0.0,
                    "volume": float(q.get("tradeVolume", 0) or 0), "oi": float(q.get("opnInterest", 0) or 0),
                    "lot_size": int(c.lotsize), "tradingsymbol": c.symbol, "token": str(c.token), "spot": spot})
    return pd.DataFrame(out)
