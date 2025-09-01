# Alert Trigger System (ATO)

An automated **Alert Triggered Order (ATO)** system for equities, futures, and options.  
It connects to Zerodha APIs to monitor live prices, trigger alerts, and execute trades automatically with full risk management.

---

## 🚀 Features
- **Alert Setup**: Define underlying, operator (>, <, >=, <=, ==), and threshold.
- **Basket Trades**: Multi-leg basket creation (EQ / FUT / CE / PE) with expiry & strike.
- **Risk Management**:
  - Per-leg TP/SL (percent, points, premium price, PnL ₹, PnL % on margin)
  - Basket-wide TP/SL (net PnL, % of margin, time-based)
  - Underlying-based exits (absolute price or point movement)
- **Execution**: Hedge-first ordering for margin efficiency.
- **Monitoring**: Live tracking via Redis ticks, expiry auto-exits, email notifications.
- **Finalization**: Automatic exits, record keeping, and completion emails.

---

## 🗂️ Project Structure
static/
css/
js/
templates/
constants.py
create_payload.py
data_generate.py
data_pulling_to_redis.py
exit_live_screener.py
global_connection.py
main_app.py
models_db.py
send_email.py
send_live_screener.py
trading_bot.py
websocket_server.py

yaml
Copy code

---

## ⚡ Quick Start

### 1. Clone Repo
```bash
git clone https://github.com/<your-username>/alert-trigger-system.git
cd alert-trigger-system
2. Setup Environment
bash
Copy code
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
3. Configure
Copy .env.example → .env

Fill in your Zerodha keys, Redis URL, SMTP, etc.

4. Run
bash
Copy code
# Start Redis first
redis-server

# Run app
python main_app.py
✅ Status
Core workflow implemented:

Alert registration & validation

Basket creation & storage in SQLite

Order execution via Zerodha

Risk checks & auto exits

Email notifications

📜 License
MIT License.

yaml
Copy code

---

👉 Do you want me to also create a **tiny `.env.example` file** so others know what environment variabl
