# AI Options Trader India — Prototype v1.0

## What this is
A local Streamlit research dashboard for Indian index OHLCV data. It computes a custom indicator stack:
- EMA 9/21 trend
- Session VWAP
- RSI 14
- MACD 12/26/9
- ATR 14
- Relative volume vs 20-bar average
- Transparent 0–5 rule-based signal score

It displays research signals and an illustrative risk budget. It does **not** select an option contract, place orders, connect to a broker, or guarantee returns.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## CSV format
Required columns:
`timestamp,symbol,open,high,low,close,volume`

Use timestamp values in a consistent timezone and bar interval. Each symbol should have chronologically ordered OHLCV bars. The prototype calculates session VWAP by calendar date in the timestamps supplied; normalize timestamps to the exchange timezone before analysis.

## Important limitations
- Rule-based indicator prototype, not a trained AI model.
- No live data feed, options-chain data, implied volatility, Greeks, expiry calendar, or contract master.
- No option premium sizing or order execution.
- Backtesting is not yet implemented; do not infer profitability from signal output.
- Real trading would require verified data, realistic costs/slippage, broker API controls, testing, authorization, and compliance review under applicable Indian regulations and broker/exchange requirements.
- Options trading is high risk; the entire premium can be lost.

## Next engineering milestones
1. Add validated historical-data ingestion and walk-forward backtesting.
2. Add option-chain/contract-master ingestion with expiry, strike, lot size, bid/ask, OI, IV and Greeks.
3. Add paper execution simulator including brokerage, taxes, spread and slippage.
4. Add monitoring, kill switch, audit trail and reconciliation.
5. Only after extensive validation, assess broker integration and regulatory permissions. Keep live execution disabled by default.
