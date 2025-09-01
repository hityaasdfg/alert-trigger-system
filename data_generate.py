import logging
import time
import threading
import random
import json
from datetime import datetime
from flask import Flask, request, jsonify
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis Configuration
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Test Redis connection
try:
    if r.ping():
        print("✅ Redis connection successful")
    else:
        print("❌ Redis ping failed")
except Exception as e:
    print("❌ Redis connection error:", e)

# Flask app
app = Flask(__name__)

# Global variables
subscribed_tokens = [256265, 131225348, 131225604]  # Default tokens
token_lock = threading.Lock()

# Dummy market data configuration
class DummyMarketData:
    def __init__(self):
        self.instruments = {
            256265: {"symbol": "NIFTY 50", "base_price": 21500, "volatility": 0.02},
            256521: {"symbol": "BANK NIFTY", "base_price": 46000, "volatility": 0.025},
            131225348: {"symbol": "RELIANCE", "base_price": 2450, "volatility": 0.03},
            131225604: {"symbol": "TCS", "base_price": 3200, "volatility": 0.025},
            15498754: {"symbol": "NIFTY25FEB21500CE", "base_price": 120, "volatility": 0.15},
            15498755: {"symbol": "NIFTY25FEB21500PE", "base_price": 85, "volatility": 0.15},
            15498756: {"symbol": "NIFTY25FEB22000CE", "base_price": 45, "volatility": 0.20},
            15498757: {"symbol": "NIFTY25FEB22000PE", "base_price": 180, "volatility": 0.18},
            15498758: {"symbol": "BANKNIFTY25FEB46000CE", "base_price": 250, "volatility": 0.18},
            15498759: {"symbol": "BANKNIFTY25FEB46000PE", "base_price": 220, "volatility": 0.18},
        }
        self.current_prices = {token: data["base_price"] for token, data in self.instruments.items()}
        self.trends = {token: 0 for token in self.instruments.keys()}

    def generate_realistic_price(self, token):
        if token not in self.instruments:
            return None
        instrument = self.instruments[token]
        current_price = self.current_prices[token]
        volatility = instrument["volatility"]
        random_change = random.gauss(0, volatility)
        trend_bias = self.trends[token] * 0.001
        new_price = max(current_price + current_price * (random_change + trend_bias), 0.05)
        if random.random() < 0.05:
            self.trends[token] = random.choice([-1, 0, 1])
        self.current_prices[token] = new_price
        return round(new_price, 2)

    def get_tick_data(self, token):
        price = self.generate_realistic_price(token)
        if price is None:
            return None
        return {
            "instrument_token": token,
            "last_price": price,
            "exchange_timestamp": datetime.now()
        }

# Global market data generator
market_data = DummyMarketData()

def simulate_ticks():
    while True:
        try:
            with token_lock:
                tokens = subscribed_tokens.copy()
            ticks = []
            for token in tokens:
                tick = market_data.get_tick_data(token)
                if tick:
                    ticks.append(tick)
            if ticks:
                on_ticks(None, ticks)
            time.sleep(random.uniform(0.1, 0.5))
        except Exception as e:
            logger.error(f"Error in tick simulation: {e}")
            time.sleep(1)

def on_ticks(ws, ticks):
    for tick in ticks:
        token = tick["instrument_token"]
        price = tick["last_price"]
        ts = tick["exchange_timestamp"]
        ts_str = ts.isoformat() if ts else str(time.time())
        key = f"tick:{token}"
        try:
            r.hset(key, mapping={"price": price, "timestamp": ts_str})
            r.expire(key, 300)
            r.publish("tick_channel", json.dumps({"token": token, "price": price, "timestamp": ts_str}))
        except redis.exceptions.ResponseError as e:
            logger.error(f"Redis write error: {e}")
        # Continuous console output for default tokens
        print(f"TICK {token} ({market_data.instruments[token]['symbol']}): ₹{price} at {ts_str}")

def add_new_token(new_token):
    global subscribed_tokens
    with token_lock:
        if new_token not in subscribed_tokens:
            subscribed_tokens.append(new_token)
            if new_token not in market_data.instruments:
                market_data.instruments[new_token] = {
                    "symbol": f"DUMMY_{new_token}",
                    "base_price": random.uniform(100, 1000),
                    "volatility": random.uniform(0.01, 0.05)
                }
                market_data.current_prices[new_token] = market_data.instruments[new_token]["base_price"]
                market_data.trends[new_token] = 0
            logger.info(f"Subscribed to new token: {new_token}")
            print(f"Subscribed to new token: {new_token}")
            return True
        return False

@app.route('/ticks', methods=['POST'])
def api_register_tokens():
    data = request.get_json() or {}
    tokens = data.get('tokens', [])
    if not isinstance(tokens, list) or not all(isinstance(t, int) for t in tokens):
        return jsonify({"error": "tokens must be a list of ints"}), 400
    results = {"subscribed": [], "skipped": []}
    for tok in tokens:
        if add_new_token(tok):
            results["subscribed"].append(tok)
        else:
            results["skipped"].append(tok)
    return jsonify(results), 200

@app.route('/add_token', methods=['POST'])
def api_add_token():
    data = request.get_json() or {}
    if 'token' not in data:
        return jsonify({"error": "Token is required"}), 400
    try:
        tok = int(data['token'])
    except ValueError:
        return jsonify({"error": "Invalid token format"}), 400
    if add_new_token(tok):
        return jsonify({"message": f"Token {tok} added successfully!"}), 200
    return jsonify({"message": f"Token {tok} already subscribed."}), 200

@app.route('/status', methods=['GET'])
def api_status():
    with token_lock:
        tokens = subscribed_tokens.copy()
    return jsonify({
        "subscribed_tokens": tokens,
        "current_prices": market_data.current_prices,
        "instruments": {t: market_data.instruments[t]["symbol"] for t in tokens},
        "redis_connected": r.ping() if r else False
    }), 200

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False)

if __name__ == "__main__":
    print("🚀 Starting Dummy Ticker Service")
    print("=" * 50)
    print("Available instruments:")
    for tok, info in market_data.instruments.items():
        print(f"  {tok}: {info['symbol']} @ ₹{info['base_price']}")
    print("=" * 50)
    tick_thread = threading.Thread(target=simulate_ticks, daemon=True)
    tick_thread.start()
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Dummy ticker service running.")
    print("✅ Console will print tick updates for subscribed tokens.")
    print("✅ Flask API on http://0.0.0.0:5000")
    print("\nAPI Endpoints:")
    print("  POST /ticks - Register tokens")
    print("  POST /add_token - Subscribe a token")
    print("  GET /status - Service status")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Service stopping...")
