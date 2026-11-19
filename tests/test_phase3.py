from datetime import date, datetime
import pandas as pd, pytest
from fastapi.testclient import TestClient
from backend import config
from backend.angel.instruments import InstrumentMaster, parse_expiry
from backend.angel.session import AngelSession, AngelError
from backend.angel import market_data
from backend.engine import PaperBroker, backtest

ROWS = [
 {"token":"99926000","symbol":"Nifty 50","name":"Nifty 50","expiry":"","strike":"-1.000000","lotsize":"1","instrumenttype":"AMXIDX","exch_seg":"NSE"},
]
for exp, lot in (("30DEC2026", 65), ("06JAN2027", 65), ("01JAN2020", 75)):
    for k in (25000, 25050, 25100, 25150, 25200):
        for t in ("CE", "PE"):
            ROWS.append({"token": f"{k}{t}{exp[:2]}", "symbol": f"NIFTY{exp}{k}{t}", "name": "NIFTY", "expiry": exp,
                         "strike": f"{k*100}.000000", "lotsize": str(lot), "instrumenttype": "OPTIDX", "exch_seg": "NFO"})

class FakeClient:
    def generateSession(self, c, p, t):
        return {"status": True, "message": "SUCCESS"} if t == "123456" else {"status": False, "message": f"bad {p}"}
    def terminateSession(self, c): return {"status": True}
    def getCandleData(self, p):
        return {"status": True, "data": [["2026-11-02T09:15:00+05:30", 100, 102, 99, 101, 1000],
                                          ["2026-11-02T09:20:00+05:30", 101, 103, 100, 102, 1200]]}
    def getMarketData(self, mode, tokens):
        if mode == "LTP":
            return {"status": True, "data": {"fetched": [{"ltp": 25103.0}]}}
        ex, toks = next(iter(tokens.items()))
        return {"status": True, "data": {"fetched": [
            {"symbolToken": t, "ltp": 100.0, "tradeVolume": 10, "opnInterest": 5,
             "depth": {"buy": [{"price": 99.5}], "sell": [{"price": 100.5}]}} for t in toks]}}

@pytest.fixture
def sess(monkeypatch):
    for k in ("ANGEL_API_KEY","ANGEL_CLIENT_CODE","ANGEL_PIN","ANGEL_TOTP_SECRET"):
        monkeypatch.setenv(k, "SECRETVALUE_" + k if k != "ANGEL_PIN" else "9999")
    s = AngelSession(connect_factory=lambda key: FakeClient(), totp_func=lambda sec: "123456")
    s.login(); return s

def test_parse_expiry():
    assert parse_expiry("30DEC2026") == date(2026, 12, 30)
    assert parse_expiry("") is None

def test_master_lot_size_and_expiries():
    m = InstrumentMaster(ROWS)
    assert m.expiries("NIFTY", date(2026, 11, 19)) == [date(2026, 12, 30), date(2027, 1, 6)]  # past expiry dropped
    assert m.lot_size("NIFTY", date(2026, 12, 30)) == 65
    assert m.spot_instrument("NIFTY")["token"] == "99926000"
    with pytest.raises(ValueError): m.options("FOO")

def test_chain_contracts_atm_window():
    m = InstrumentMaster(ROWS)
    c = m.chain_contracts("NIFTY", date(2026, 12, 30), 25103, strikes_each_side=1)
    assert sorted(c.strike_price.unique()) == [25050, 25100, 25150]
    assert set(c.option_type) == {"CE", "PE"}

def test_login_missing_credentials(monkeypatch):
    for k in ("ANGEL_API_KEY","ANGEL_CLIENT_CODE","ANGEL_PIN","ANGEL_TOTP_SECRET"): monkeypatch.delenv(k, raising=False)
    with pytest.raises(AngelError, match="Missing"): AngelSession(lambda k: FakeClient()).login()

def test_login_error_never_leaks_pin(monkeypatch):
    monkeypatch.setenv("ANGEL_API_KEY","k"); monkeypatch.setenv("ANGEL_CLIENT_CODE","C1")
    monkeypatch.setenv("ANGEL_PIN","4321"); monkeypatch.setenv("ANGEL_TOTP_SECRET","s")
    with pytest.raises(AngelError) as e:
        AngelSession(lambda k: FakeClient(), lambda s: "000000").login()
    assert "4321" not in str(e.value)

def test_candles_schema(sess):
    df = market_data.fetch_candles(sess, "NSE", "99926000", "NIFTY", "FIVE_MINUTE",
                                   datetime(2026, 11, 2), datetime(2026, 11, 3))
    assert list(df.columns) == ["timestamp","symbol","open","high","low","close","volume"]
    assert len(df) == 2 and str(df.timestamp.iloc[0]) == "2026-11-02 09:15:00"
    with pytest.raises(ValueError): market_data.fetch_candles(sess,"NSE","1","N","BAD",datetime(2026,1,1),datetime(2026,1,2))

def test_option_chain_snapshot_matches_phase2_schema(sess):
    m = InstrumentMaster(ROWS)
    df = market_data.option_chain_snapshot(sess, m, "NIFTY", strikes_each_side=1, now=datetime(2026, 11, 19, 10, 0))
    assert len(df) == 6 and set(df.expiry) == {"2026-12-30"} and (df.lot_size == 65).all()
    from backend.engine import chain_snapshot   # Phase 2 code must accept it
    assert len(chain_snapshot(df, "NIFTY")) == 6

def test_live_orders_hard_disabled_and_no_order_routes():
    assert config.LIVE_ORDERS_ENABLED is False
    from backend.main import app
    paths = [r.path.lower() for r in app.routes]
    assert not any(x in p for p in paths for x in ("place","live","angel/order"))
    for name in dir(AngelSession): assert "order" not in name.lower()
    for name in dir(market_data): assert "place" not in name.lower()

def test_api_health_never_exposes_secrets(monkeypatch):
    monkeypatch.setenv("ANGEL_PIN", "7777")
    from backend.main import app
    c = TestClient(app)
    body = c.get("/health").text + c.get("/angel/status").text
    assert "7777" not in body and c.get("/health").json()["live_orders_enabled"] is False

def test_kill_switch_blocks_paper_orders():
    b = PaperBroker(); b.kill_switch = True
    with pytest.raises(ValueError, match="kill switch"):
        b.place({"symbol":"X","expiry":"2026-12-30","lot_size":65}, "BUY", 65, 100, 90)

def test_phase2_still_works():
    b = PaperBroker()
    o = b.place({"symbol":"X","expiry":"2026-12-30","lot_size":65}, "BUY", 65, 100, 97)
    assert b.close_position(o["id"], 110)["realized_pnl"] == 650
    assert backtest(pd.DataFrame({"timestamp":[],"symbol":[],"open":[],"high":[],"low":[],"close":[],"volume":[]}))["summary"]["trades"] == 0
