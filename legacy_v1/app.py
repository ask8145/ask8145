import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="AI Options Trader India", page_icon="📈", layout="wide")

CAPITAL = 25000.0
st.title("📈 AI Options Trader — India")
st.caption("Prototype v1.0 · Research and paper-trading only · No broker connection or live orders")

with st.sidebar:
    st.header("Configuration")
    capital = st.number_input("Paper capital (₹)", min_value=1000, value=25000, step=1000)
    risk_pct = st.slider("Risk budget per trade (%)", 0.25, 2.0, 1.0, 0.25)
    daily_loss_pct = st.slider("Daily stop (%)", 0.5, 5.0, 2.0, 0.5)
    min_score = st.slider("Minimum signal score", 1, 5, 3)
    st.info("Defaults are conservative research settings, not a profit forecast or personalized investment advice.")

st.subheader("1 · Upload underlying-index OHLCV data")
st.write("CSV columns required: `timestamp, symbol, open, high, low, close, volume`.")
uploaded = st.file_uploader("Upload OHLCV CSV", type=["csv"])

def indicators(df):
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["timestamp", "close", "high", "low", "volume"]).sort_values(["symbol", "timestamp"])
    out = []
    for symbol, g in d.groupby("symbol", sort=False):
        g = g.copy()
        g["ema_fast"] = g["close"].ewm(span=9, adjust=False).mean()
        g["ema_slow"] = g["close"].ewm(span=21, adjust=False).mean()
        tp = (g["high"] + g["low"] + g["close"]) / 3
        day = g["timestamp"].dt.date
        cum_pv = (tp * g["volume"]).groupby(day).cumsum()
        cum_vol = g["volume"].groupby(day).cumsum().replace(0, np.nan)
        g["vwap"] = cum_pv / cum_vol
        delta = g["close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        g["rsi"] = 100 - (100 / (1 + rs))
        ema12 = g["close"].ewm(span=12, adjust=False).mean()
        ema26 = g["close"].ewm(span=26, adjust=False).mean()
        g["macd"] = ema12 - ema26
        g["macd_signal"] = g["macd"].ewm(span=9, adjust=False).mean()
        prev_close = g["close"].shift()
        tr = pd.concat([(g["high"]-g["low"]), (g["high"]-prev_close).abs(),
                        (g["low"]-prev_close).abs()], axis=1).max(axis=1)
        g["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()
        g["vol_sma20"] = g["volume"].rolling(20).mean()
        g["volume_ratio"] = g["volume"] / g["vol_sma20"].replace(0, np.nan)
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

def score_row(r):
    long_checks = [
        r["ema_fast"] > r["ema_slow"],
        r["close"] > r["vwap"],
        r["rsi"] > 50 and r["rsi"] < 72,
        r["macd"] > r["macd_signal"],
        r["volume_ratio"] >= 1.2
    ]
    short_checks = [
        r["ema_fast"] < r["ema_slow"],
        r["close"] < r["vwap"],
        r["rsi"] < 50 and r["rsi"] > 28,
        r["macd"] < r["macd_signal"],
        r["volume_ratio"] >= 1.2
    ]
    ls, ss = sum(bool(x) for x in long_checks), sum(bool(x) for x in short_checks)
    if ls >= ss:
        return pd.Series([ls, "BULLISH" if ls >= 3 else "NO TRADE"])
    return pd.Series([ss, "BEARISH" if ss >= 3 else "NO TRADE"])

if uploaded:
    try:
        raw = pd.read_csv(uploaded)
        required = {"timestamp","symbol","open","high","low","close","volume"}
        missing = required - set(raw.columns)
        if missing:
            st.error("Missing columns: " + ", ".join(sorted(missing)))
        else:
            data = indicators(raw)
            if data.empty:
                st.warning("No usable rows found.")
            else:
                scored = data.apply(score_row, axis=1)
                data["score"] = scored[0].astype(int)
                data["signal"] = scored[1]
                latest = data.sort_values("timestamp").groupby("symbol").tail(1)
                st.subheader("2 · Latest research signals")
                show_cols = ["timestamp","symbol","close","ema_fast","ema_slow","vwap","rsi","atr","volume_ratio","score","signal"]
                st.dataframe(latest[show_cols].sort_values("symbol"), use_container_width=True)
                st.subheader("3 · Risk planning calculator")
                candidates = latest[latest["signal"].isin(["BULLISH","BEARISH"]) & (latest["score"] >= min_score)]
                if candidates.empty:
                    st.info("No setup meets the current signal threshold. No trade is a valid outcome.")
                else:
                    for _, r in candidates.iterrows():
                        direction = "CALL research setup" if r["signal"] == "BULLISH" else "PUT research setup"
                        risk_cash = capital * risk_pct / 100
                        stop_distance = max(float(r["atr"]) * 1.5, 0) if pd.notna(r["atr"]) else np.nan
                        st.write(f"**{r['symbol']} · {direction} · Score {r['score']}/5**")
                        if pd.notna(stop_distance) and stop_distance > 0:
                            st.write(f"Underlying reference: {r['close']:.2f} · ATR-based reference distance: {stop_distance:.2f} points")
                        st.write(f"Illustrative maximum risk budget: ₹{risk_cash:,.0f}. This is not an options premium quantity; option premium, lot size, slippage and contract details must be supplied and validated separately.")
                st.subheader("4 · Indicator history")
                chosen = st.selectbox("Choose index", sorted(data["symbol"].dropna().unique()))
                hist = data[data["symbol"] == chosen].tail(250).set_index("timestamp")
                st.line_chart(hist[["close","ema_fast","ema_slow","vwap"]].dropna())
                st.caption("Signal rules are deterministic research heuristics, not machine-learning predictions. Validate with out-of-sample data, realistic brokerage, taxes, slippage and expiry effects.")
    except Exception as e:
        st.error(f"Could not process CSV: {e}")
else:
    st.info("Upload a CSV to calculate indicators and research signals. No live market feed is connected.")
    sample = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01 09:15", periods=3, freq="5min"),
        "symbol": ["NIFTY"]*3,
        "open": [26000,26005,26010], "high": [26010,26020,26025],
        "low": [25995,26000,26005], "close": [26005,26012,26020],
        "volume": [10000,12000,15000]
    })
    st.download_button("Download sample CSV", sample.to_csv(index=False), "sample_ohlcv.csv", "text/csv")

st.divider()
st.subheader("Safety controls planned for later versions")
st.markdown("""
- Hard daily loss lockout and per-trade risk cap.
- Max open positions, max trades/day and cooldown after consecutive losses.
- Contract-master validation for symbol, expiry, strike, lot size and tick size.
- Limit-price and spread checks; reject stale or incomplete market data.
- Kill switch, broker-side order reconciliation and audit logs.
- Paper-trading and out-of-sample validation before any live execution.
""")
st.warning("This prototype does not place orders, connect to a broker, promise daily income, or recommend a specific trade. Options can lose the entire premium and may involve additional execution risks.")
