# Windows setup (step by step)

## One-time install
1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/ — tick **"Add python.exe to PATH"** on the first screen.
2. Install Git for Windows (https://git-scm.com) if you want to pull this code from GitHub; otherwise just unzip the folder.
3. Open **PowerShell** and go to the project folder, e.g. `cd C:\Users\YOU\ai_options_trader`.

## Create the environment and install
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
(If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.)

## Run the tests (no Angel One account needed)
```powershell
python -m pytest -q
```
You should see `11 passed`.

## Add your Angel One details (safely)
1. Copy `.env.example` to a new file named exactly `.env` (`copy .env.example .env`), open it in Notepad.
2. Fill in `ANGEL_API_KEY` (from the SmartAPI portal), `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, and `ANGEL_TOTP_SECRET`
   (the text secret shown when you enable TOTP at smartapi.angelone.in — **not** the 6-digit code).
3. Never email, screenshot, upload or commit `.env`. If you ever do, regenerate the key/TOTP immediately.
4. In your SmartAPI app settings, check whether Angel One requires a registered static IP for your usage; follow their current rules.

## Start the app
Window 1: `uvicorn backend.main:app --host 127.0.0.1 --port 8000`
Window 2: `streamlit run web/dashboard.py`

## Try Phase 3 (open http://127.0.0.1:8000/docs in your browser)
1. `POST /angel/login` → expect `{"logged_in": true}`.
2. `GET /angel/contracts/NIFTY` → real expiries and lot size.
3. `GET /angel/candles/NIFTY?interval=FIVE_MINUTE&days=5`
4. `GET /angel/option-chain/NIFTY`
5. `POST /safety/kill-switch/on` to test the kill switch; `/off` to clear.
Run it **after market hours** first; some quotes may be stale or empty then.

Live trading is not possible in this version.
