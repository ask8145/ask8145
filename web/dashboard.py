import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="AI Options Trader", page_icon="📊", layout="wide")
API = st.sidebar.text_input("Backend URL", "http://127.0.0.1:8000")
st.title("📊 AI Options Trader — Angel One Edition")
st.caption("Phase 2 · Backtesting, options-chain snapshots and paper trading · LIVE ORDERS DISABLED")

tabs = st.tabs(["Backtesting", "Options chain", "Paper trading", "System"])
with tabs[0]:
    st.subheader("Historical strategy test")
    f = st.file_uploader("Upload OHLCV CSV", type="csv", key="bt")
    a,b,c = st.columns(3)
    cap = a.number_input("Capital ₹", 1000, 10000000, 25000, 1000)
    risk = b.slider("Risk budget %", .25, 2.0, 1.0, .25)
    costs = c.number_input("Estimated friction (bps)", 0.0, 100.0, 10.0)
    if f and st.button("Run backtest"):
        try:
            res = requests.post(f"{API}/backtest", files={"file":(f.name,f.getvalue(),"text/csv")},
                                params={"capital":cap,"risk_pct":risk,"cost_bps":costs}, timeout=60)
            res.raise_for_status()
            out = res.json()
            st.json(out["summary"])
            st.dataframe(pd.DataFrame(out["trades"]), use_container_width=True)
        except Exception as e: st.error(str(e))
with tabs[1]:
    st.subheader("Options-chain snapshot")
    f2 = st.file_uploader("Upload chain CSV", type="csv", key="chain")
    u = st.selectbox("Underlying", ["NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY","SENSEX","BANKEX"])
    expiry = st.text_input("Expiry filter (optional)")
    if f2 and st.button("Load chain"):
        try:
            res = requests.post(f"{API}/options-chain", files={"file":(f2.name,f2.getvalue(),"text/csv")},
                                params={"underlying":u,"expiry":expiry or None}, timeout=30)
            res.raise_for_status()
            st.dataframe(pd.DataFrame(res.json()["data"]), use_container_width=True)
            st.caption(res.json()["note"])
        except Exception as e: st.error(str(e))
with tabs[2]:
    st.subheader("Paper account")
    st.warning("Simulated orders only. In-memory account resets when backend restarts.")
    try:
        acc = requests.get(f"{API}/paper/account", timeout=5).json()
        st.json(acc)
    except Exception as e: st.info(f"Start backend to view paper account: {e}")
    with st.form("paper_order"):
        symbol = st.text_input("Contract symbol", "NIFTY26DEC25000CE")
        expiry2 = st.text_input("Expiry", "2026-12-31")
        lot = st.number_input("Lot size", 1, 1000, 65)
        qty = st.number_input("Quantity (multiple of lot)", 1, 10000, 65)
        price = st.number_input("Entry premium ₹", .05, 100000.0, 100.0)
        stop = st.number_input("Stop premium ₹", .01, 99999.0, 80.0)
        submitted = st.form_submit_button("Place simulated BUY")
        if submitted:
            try:
                r=requests.post(f"{API}/paper/orders",json={"symbol":symbol,"expiry":expiry2,"lot_size":lot,
                    "qty":qty,"price":price,"stop_price":stop},timeout=10)
                r.raise_for_status(); st.success(r.json())
            except Exception as e: st.error(str(e))
with tabs[3]:
    st.subheader("System status")
    try: st.json(requests.get(f"{API}/health",timeout=5).json())
    except Exception as e: st.error(str(e))
    st.markdown("**Angel One SmartAPI:** adapter is not authenticated or connected in this phase. Keep API keys and TOTP secrets on a secured backend; never place them in Android or browser code.")
