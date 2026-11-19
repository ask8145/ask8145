# Phase 3 plan — Angel One SmartAPI, READ-ONLY

Goal: real data in, zero orders out.

1. Config & secrets (`backend/config.py`, `.env`): credentials only from `.env`; API only reports yes/no for each.
2. Login (`angel/session.py`): API key + client code + PIN + auto-generated TOTP; secrets redacted from errors; request throttling.
3. Instrument master (`angel/instruments.py`): download Angel's public scrip master, cache 12h, read real lot sizes, expiries, strikes (÷100) and tokens. Nothing hard-coded.
4. Market data (`angel/market_data.py`): historical candles (chunked to Angel's per-interval limits, output in the Phase 1/2 CSV schema), index spot LTP, option-chain snapshot (ATM ± N strikes, bid/ask/OI/volume, same schema as Phase 2 chain input + lot_size).
5. API routes: `/angel/login|logout|status`, `/angel/contracts/{u}`, `/angel/candles/{u}`, `/angel/option-chain/{u}`, `/safety/kill-switch/{on|off}`.
6. Safety: `LIVE_ORDERS_ENABLED = False` is a constant in code; no order function or route exists; a test fails if one is added.
7. Tests use a fake Angel client (no network, no real credentials).

Out of scope until you approve: WebSocket streaming, order placement, strategy automation (Phase 4).
