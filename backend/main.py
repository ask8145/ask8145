from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
import pandas as pd
from io import BytesIO
from datetime import datetime, date
from . import config
from .engine import backtest, chain_snapshot, PaperBroker
from .angel.session import AngelSession, AngelError
from .angel.instruments import InstrumentMaster
from .angel import market_data

config.load_dotenv()
angel = AngelSession()
_master: InstrumentMaster | None = None

def get_master() -> InstrumentMaster:
    global _master
    if _master is None:
        _master = InstrumentMaster.load()
    return _master

app = FastAPI(title="AI Options Trader API", version="3.0.0",
              description="Research, backtesting, paper trading and read-only Angel One data. No live order route.")

paper = PaperBroker(25000, max_risk_pct=1.0, daily_loss_pct=2.0)


class PaperClose(BaseModel):
    order_id: int = Field(gt=0)
    exit_price: float = Field(gt=0)

class PaperOrder(BaseModel):
    symbol: str
    expiry: str
    lot_size: int = Field(gt=0)
    side: str = "BUY"
    qty: int = Field(gt=0)
    price: float = Field(gt=0)
    stop_price: float = Field(gt=0)

@app.get("/health")
def health():
    return {"status":"ok","mode":"PAPER_ONLY","live_orders_enabled":config.LIVE_ORDERS_ENABLED,
            "angel_logged_in":angel.is_logged_in,"kill_switch":paper.kill_switch,
            "credentials_configured":config.credentials_present()}

@app.post("/backtest")
async def run_backtest(file: UploadFile = File(...), capital: float = 25000,
                       risk_pct: float = 1.0, cost_bps: float = 10.0, min_score: int = 3):
    try:
        df = pd.read_csv(BytesIO(await file.read()))
        return backtest(df, capital, risk_pct, cost_bps, min_score)
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/options-chain")
async def options_chain(file: UploadFile = File(...), underlying: str = "NIFTY", expiry: str | None = None):
    try:
        df = pd.read_csv(BytesIO(await file.read()))
        return {"data": chain_snapshot(df, underlying, expiry),
                "note":"Snapshot from uploaded data. Not a live Angel One feed."}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/paper/orders")
def paper_order(order: PaperOrder):
    try:
        return paper.place({"symbol":order.symbol,"expiry":order.expiry,"lot_size":order.lot_size},
                           order.side, order.qty, order.price, order.stop_price)
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/paper/close")
def paper_close(close: PaperClose):
    try:
        return paper.close_position(close.order_id, close.exit_price)
    except Exception as e:
        raise HTTPException(400, str(e))

@app.get("/paper/account")
def paper_account():
    return {"account":paper.account.as_dict(),
            "mark_to_market":paper.mark_to_market({}),
            "orders":paper.orders}

@app.post("/paper/reset")
def reset_paper():
    global paper
    paper = PaperBroker(25000, max_risk_pct=1.0, daily_loss_pct=2.0)
    return {"status":"reset","mode":"PAPER_ONLY"}

# ---------------- Phase 3: Angel One (READ-ONLY data) ----------------
def _angel_call(fn):
    try:
        return fn()
    except (AngelError, ValueError) as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, "Angel One request failed: " + type(e).__name__)

@app.post("/angel/login")
def angel_login():
    return _angel_call(angel.login)

@app.post("/angel/logout")
def angel_logout():
    angel.logout(); return {"logged_in": False}

@app.get("/angel/status")
def angel_status():
    return {"logged_in": angel.is_logged_in, "credentials_configured": config.credentials_present(),
            "live_orders_enabled": config.LIVE_ORDERS_ENABLED}

@app.post("/angel/instruments/refresh")
def refresh_instruments():
    global _master
    def go():
        global _master
        _master = InstrumentMaster.load(force=True)
        return {"instruments": len(_master.df)}
    return _angel_call(go)

@app.get("/angel/contracts/{underlying}")
def contract_info(underlying: str):
    """Verified expiries and lot size straight from Angel One's instrument master."""
    def go():
        m = get_master(); u = underlying.upper()
        exps = m.expiries(u)
        return {"underlying": u, "expiries": [e.isoformat() for e in exps[:8]],
                "lot_size": m.lot_size(u, exps[0]) if exps else None}
    return _angel_call(go)

@app.get("/angel/candles/{underlying}")
def candles(underlying: str, interval: str = "FIVE_MINUTE", days: int = 5):
    def go():
        m = get_master(); spot = m.spot_instrument(underlying)
        if not spot: raise ValueError("Spot instrument not found.")
        end = datetime.now(); start = end - __import__("datetime").timedelta(days=max(1, min(days, 365)))
        df = market_data.fetch_candles(angel, spot["exch_seg"], spot["token"], underlying.upper(), interval, start, end)
        return {"rows": len(df), "csv_schema": "timestamp,symbol,open,high,low,close,volume",
                "data": df.assign(timestamp=df.timestamp.astype(str)).to_dict("records")}
    return _angel_call(go)

@app.get("/angel/option-chain/{underlying}")
def live_chain(underlying: str, expiry: str | None = None, strikes: int = 10):
    def go():
        exp = date.fromisoformat(expiry) if expiry else None
        df = market_data.option_chain_snapshot(angel, get_master(), underlying, exp, max(1, min(strikes, 25)))
        return {"count": len(df), "data": df.to_dict("records"),
                "note": "Snapshot from Angel One; verify freshness before use. Read-only."}
    return _angel_call(go)

# ---------------- Safety ----------------
@app.post("/safety/kill-switch/{state}")
def kill_switch(state: str):
    if state not in ("on", "off"):
        raise HTTPException(400, "Use 'on' or 'off'.")
    paper.kill_switch = state == "on"
    return {"kill_switch": paper.kill_switch}

# Deliberately no live order endpoint in this build.
