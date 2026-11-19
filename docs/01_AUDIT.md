# Audit of the uploaded code (v1 + Phase 2)

**What exists and works:** indicator engine (EMA/VWAP/RSI/MACD/ATR/rel-volume), 0–5 signal score,
next-bar-open backtester, chain CSV normaliser, in-memory paper broker (lot check, per-trade risk cap,
daily-loss lock), FastAPI API, Streamlit dashboard, Flutter scaffold. v1 (`legacy_v1/`) is the older
single-file prototype, kept for reference only.

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | No automated tests existed | High | Fixed: `tests/` added (11 tests) |
| 2 | Angel One adapter was a placeholder | — | Done in Phase 3 |
| 3 | Dashboard hard-codes NIFTY lot size 65 and contract text | Medium | Open: Phase 4 should fill from `/angel/contracts/{underlying}` |
| 4 | Dashboard `min_score` slider is not sent to the backtest API | Low | Open |
| 5 | Stop-loss is only a risk calculation; nothing monitors price and exits | High | Open: Phase 4 trade monitor |
| 6 | Daily-loss lock is only evaluated when `/paper/account` is called; `day_start_equity` never resets each day | High | Open: Phase 4 |
| 7 | `mark_to_market({})` uses entry price, so open P&L is never real | Medium | Open: Phase 4 will feed live LTPs |
| 8 | Paper account is in-memory (lost on restart) | Medium | Open: add SQLite in Phase 4 |
| 9 | Backtest is underlying points, not option-premium P&L; costs are a rough proxy | Medium | Documented limitation |
| 10 | No emergency kill switch | High | Fixed: `/safety/kill-switch/on|off` blocks new paper orders |
| 11 | No auth on the API (anyone who can reach port 8000 can use it) | High before deployment | Open: Phase 5; keep bound to 127.0.0.1 |
| 12 | Android app is a static screen with no API calls | Medium | Open: Phase 5 |
| 13 | Only long-option BUY supported | Design | Matches ₹25k/moderate risk |
