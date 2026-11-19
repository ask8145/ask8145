# AI Options Trader India — Phase 2

## Included
- FastAPI backend for historical backtesting, option-chain CSV snapshots and paper orders.
- Streamlit website dashboard.
- Flutter Android UI scaffold.
- Custom indicator engine: EMA 9/21, session VWAP, RSI-14, MACD 12/26/9, ATR-14, relative volume.
- Paper broker with lot-size validation, long-option premium debit, per-trade risk cap and daily drawdown lock.
- CSV templates.

## Run
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```
In another terminal:
```bash
streamlit run web/dashboard.py
```
API docs: http://127.0.0.1:8000/docs

## Backtest input
Use `data/ohlcv_template.csv` as a schema example. Columns:
`timestamp,symbol,open,high,low,close,volume`.

The backtester uses previous-bar signals and next-bar open execution to avoid same-bar lookahead. It is a points-based underlying-index strategy test, not an options premium return test. Costs are a simple friction proxy, not a broker/exchange fee schedule. No expiry, Greeks, option premium, lot sizing or realistic option fills are included in that backtest yet.

## Options chain input
Use `data/options_chain_template.csv`. Columns:
`timestamp,underlying,expiry,strike,option_type,ltp,bid,ask,volume,oi`.
The chain view is a snapshot from uploaded data, not a live broker feed. Live Angel One integration must verify current scrip master, exchange tokens, subscription limits, quote freshness and API limits.

## Paper trading
Paper orders are long-option BUYs only; open positions can be closed at a supplied simulated exit premium. Quantity must be a lot multiple. Risk is calculated as `(entry premium - stop premium) * quantity`; this is a simplified max-loss-at-stop estimate and does not model gaps, slippage, brokerage, taxes or partial fills. Paper account is in-memory and resets when backend restarts.

## Angel One integration status
Broker selected: Angel One SmartAPI. This build intentionally does not authenticate or place live orders. Add a server-side adapter only after verifying current SmartAPI docs, credentials handling, TOTP/session lifecycle, exchange rules, broker permissions and SEBI/exchange retail algo requirements. Never put API key, client code, PIN or TOTP secret in Flutter or browser source. Use environment secrets and authenticated backend sessions.

## Compliance and risk
This is software prototyping, not investment advice. Options are high risk and the entire premium can be lost. No daily profit is promised. Before live automation, obtain broker confirmation of eligibility and required registrations/approvals; implement exchange/broker mandated controls, static IP or other applicable requirements, order-rate limits, audit logs, kill switch, reconciliation, monitoring and independent security review. Do not assume a personal API strategy is exempt from current rules.
