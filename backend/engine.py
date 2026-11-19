from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd
import numpy as np

REQUIRED_OHLCV = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
REQUIRED_CHAIN = {"timestamp", "underlying", "expiry", "strike", "option_type", "ltp", "bid", "ask", "volume", "oi"}

def validate_columns(df: pd.DataFrame, required: set[str]) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Missing columns: " + ", ".join(sorted(missing)))

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, REQUIRED_OHLCV)
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["timestamp", "symbol", "high", "low", "close", "volume"])
    d = d.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    chunks = []
    for symbol, g in d.groupby("symbol", sort=False):
        g = g.copy()
        g["ema9"] = g.close.ewm(span=9, adjust=False).mean()
        g["ema21"] = g.close.ewm(span=21, adjust=False).mean()
        tp = (g.high + g.low + g.close) / 3
        session = g.timestamp.dt.date
        g["vwap"] = (tp * g.volume).groupby(session).cumsum() / g.volume.groupby(session).cumsum().replace(0, np.nan)
        delta = g.close.diff()
        up = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        down = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = up / down.replace(0, np.nan)
        g["rsi14"] = 100 - 100 / (1 + rs)
        macd = g.close.ewm(span=12, adjust=False).mean() - g.close.ewm(span=26, adjust=False).mean()
        g["macd"] = macd
        g["macd_signal"] = macd.ewm(span=9, adjust=False).mean()
        prev = g.close.shift()
        tr = pd.concat([(g.high-g.low), (g.high-prev).abs(), (g.low-prev).abs()], axis=1).max(axis=1)
        g["atr14"] = tr.ewm(alpha=1/14, adjust=False).mean()
        g["vol_sma20"] = g.volume.rolling(20, min_periods=5).mean()
        g["relative_volume"] = g.volume / g.vol_sma20.replace(0, np.nan)
        chunks.append(g)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

def signal_for_row(r) -> tuple[str, int]:
    bullish = [
        r.ema9 > r.ema21,
        r.close > r.vwap,
        50 < r.rsi14 < 72,
        r.macd > r.macd_signal,
        r.relative_volume >= 1.2,
    ]
    bearish = [
        r.ema9 < r.ema21,
        r.close < r.vwap,
        28 < r.rsi14 < 50,
        r.macd < r.macd_signal,
        r.relative_volume >= 1.2,
    ]
    b, s = sum(bool(x) for x in bullish), sum(bool(x) for x in bearish)
    if b >= 3 and b > s:
        return "BULLISH", b
    if s >= 3 and s > b:
        return "BEARISH", s
    return "NO_TRADE", max(b, s)

def make_signals(df: pd.DataFrame) -> pd.DataFrame:
    d = add_indicators(df)
    if d.empty:
        return d
    sig = d.apply(signal_for_row, axis=1)
    d["signal"] = [x[0] for x in sig]
    d["score"] = [x[1] for x in sig]
    return d

def backtest(df: pd.DataFrame, initial_capital: float = 25000,
             risk_pct: float = 1.0, cost_bps: float = 10.0,
             min_score: int = 3) -> dict:
    """Underlying points-based signal backtest, not option-premium P&L.
    Entry at next bar open; exit on opposite signal or end. Costs are
    modeled in basis points of underlying notional proxy and are illustrative.
    """
    if initial_capital <= 0 or not 0 < risk_pct <= 2:
        raise ValueError("Capital must be positive and risk_pct must be in (0, 2].")
    d = make_signals(df)
    if len(d) < 3:
        return {"trades": [], "summary": {"trades": 0, "net_points": 0.0, "win_rate_pct": 0.0,
                "initial_capital": initial_capital, "note": "Not enough bars."}}
    trades = []
    for symbol, g in d.groupby("symbol"):
        g = g.sort_values("timestamp").reset_index(drop=True)
        side, entry, entry_time = 0, None, None
        for i in range(1, len(g)):
            prev = g.iloc[i-1]
            cur = g.iloc[i]
            target_side = 1 if prev.signal == "BULLISH" and prev.score >= min_score else (-1 if prev.signal == "BEARISH" and prev.score >= min_score else 0)
            if side == 0 and target_side:
                side, entry, entry_time = target_side, float(cur.open), cur.timestamp
            elif side and (target_side == -side or i == len(g)-1):
                exit_price = float(cur.open if target_side == -side else cur.close)
                gross = (exit_price - entry) * side
                # transparent friction approximation; not exchange fee calculation
                friction = (abs(entry) + abs(exit_price)) * cost_bps / 10000
                trades.append({"symbol": str(symbol), "entry_time": str(entry_time), "exit_time": str(cur.timestamp),
                               "side": "LONG" if side == 1 else "SHORT", "entry": entry, "exit": exit_price,
                               "gross_points": gross, "estimated_cost_points": friction, "net_points": gross-friction})
                side, entry, entry_time = 0, None, None
    wins = sum(t["net_points"] > 0 for t in trades)
    net = sum(t["net_points"] for t in trades)
    return {"trades": trades, "summary": {
        "trades": len(trades), "wins": wins, "losses": len(trades)-wins,
        "win_rate_pct": round(100*wins/len(trades), 2) if trades else 0.0,
        "net_points": round(net, 2), "initial_capital": initial_capital,
        "risk_budget_per_trade": round(initial_capital*risk_pct/100, 2),
        "note": "Underlying-index points simulation only; not option P&L. No guarantee of future results."
    }}

def normalize_option_chain(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, REQUIRED_CHAIN)
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d.timestamp, errors="coerce")
    for c in ["strike", "ltp", "bid", "ask", "volume", "oi"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["option_type"] = d.option_type.astype(str).str.upper()
    d = d.dropna(subset=["timestamp","underlying","expiry","strike","ltp","bid","ask"])
    d = d[d.option_type.isin(["CE","PE"])]
    d["spread"] = d.ask - d.bid
    d["spread_pct"] = np.where(d.ltp > 0, d.spread / d.ltp * 100, np.nan)
    d["underlying"] = d.underlying.astype(str).str.upper()
    return d.sort_values(["underlying","expiry","strike","option_type"])

def chain_snapshot(df: pd.DataFrame, underlying: str, expiry: Optional[str] = None) -> list[dict]:
    d = normalize_option_chain(df)
    d = d[d.underlying == underlying.upper()]
    if expiry:
        d = d[d.expiry.astype(str) == str(expiry)]
    if d.empty:
        return []
    latest_ts = d.timestamp.max()
    d = d[d.timestamp == latest_ts]
    return d[["timestamp","underlying","expiry","strike","option_type","ltp","bid","ask","spread_pct","volume","oi"]].to_dict("records")

@dataclass
class PaperAccount:
    starting_cash: float = 25000.0
    cash: float = 25000.0
    realized_pnl: float = 0.0
    def as_dict(self):
        return asdict(self)

class PaperBroker:
    """In-memory paper simulator. Restart resets state; persist only after DB added."""
    def __init__(self, starting_cash=25000.0, max_risk_pct=1.0, daily_loss_pct=2.0):
        self.account = PaperAccount(starting_cash, starting_cash, 0.0)
        self.max_risk_pct = max_risk_pct
        self.daily_loss_pct = daily_loss_pct
        self.positions = []
        self.orders = []
        self.day_start_equity = starting_cash
        self.locked = False
        self.kill_switch = False

    def place(self, contract: dict, side: str, qty: int, price: float, stop_price: float):
        if self.kill_switch:
            raise ValueError("Emergency kill switch is ON. No new orders allowed.")
        if self.locked:
            raise ValueError("Paper account locked by daily loss guard.")
        if side not in {"BUY","SELL"} or qty <= 0 or price <= 0:
            raise ValueError("Invalid side, quantity or price.")
        if side != "BUY":
            raise ValueError("Prototype supports long option paper positions only.")
        if not contract.get("symbol") or not contract.get("expiry") or contract.get("lot_size") is None:
            raise ValueError("Contract symbol, expiry and lot_size are required.")
        lot = int(contract["lot_size"])
        if qty % lot:
            raise ValueError(f"Quantity must be a multiple of lot size ({lot}).")
        if stop_price <= 0 or stop_price >= price:
            raise ValueError("For long options, stop_price must be positive and below entry price.")
        risk = (price-stop_price)*qty
        risk_cap = self.account.starting_cash*self.max_risk_pct/100
        if risk > risk_cap:
            raise ValueError(f"Trade risk ₹{risk:.2f} exceeds configured per-trade cap ₹{risk_cap:.2f}.")
        debit = price*qty
        if debit > self.account.cash:
            raise ValueError("Insufficient paper cash.")
        order = {"id": len(self.orders)+1, "status":"FILLED_SIMULATED", "side":side,
                 "qty":qty,"entry_price":price,"stop_price":stop_price, **contract}
        self.account.cash -= debit
        self.positions.append(order.copy())
        self.orders.append(order.copy())
        return order

    def close_position(self, order_id: int, exit_price: float):
        if exit_price <= 0:
            raise ValueError("Exit price must be positive.")
        pos = next((p for p in self.positions if p["id"] == order_id), None)
        if pos is None:
            raise ValueError("Open paper position not found.")
        proceeds = exit_price * pos["qty"]
        pnl = (exit_price - pos["entry_price"]) * pos["qty"]
        self.account.cash += proceeds
        self.account.realized_pnl += pnl
        self.positions.remove(pos)
        result = {"id": order_id, "status": "CLOSED_SIMULATED",
                  "exit_price": exit_price, "realized_pnl": round(pnl, 2)}
        self.orders.append(result)
        return result

    def mark_to_market(self, prices: dict[str,float]):
        value = 0.0
        for p in self.positions:
            ltp = float(prices.get(p["symbol"], p["entry_price"]))
            value += ltp*p["qty"]
        equity = self.account.cash + value
        drawdown = max(0.0, self.day_start_equity-equity)
        if drawdown >= self.day_start_equity*self.daily_loss_pct/100:
            self.locked = True
        return {"cash":round(self.account.cash,2), "positions_value":round(value,2),
                "equity":round(equity,2), "realized_pnl":round(self.account.realized_pnl,2),
                "day_drawdown":round(drawdown,2), "locked":self.locked,
                "positions":self.positions}
