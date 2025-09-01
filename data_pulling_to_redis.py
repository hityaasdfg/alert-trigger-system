import logging
import time
import threading
from flask import Flask, request, jsonify
from kiteconnect import KiteTicker, KiteConnect
import pandas as pd
logging.basicConfig(level=logging.DEBUG)
import redis
import json
from constants import ACCESS_TOKEN_PATH, INSTRUMENTS_CSV_PATH
    

# Read access token
with open(ACCESS_TOKEN_PATH) as f:
    access_token = f.read().strip()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_key = 'zuuxkho8imp70m8c'
# print (access_token)
# exit(0)
kws = KiteTicker(api_key, access_token)
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)



REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


try:
    # Test connection with ping
    if r.ping():
        print("✅ Redis connection successful")
    else:
        print("❌ Redis ping failed")
except Exception as e:
    print("❌ Redis connection error:", e)
    


def get_instrument_id(symbol):
    """Retrieve the instrument token for a given trading symbol."""
    return data[data['tradingsymbol'] == symbol]['instrument_token'].iloc[0]

instrument_csv_path = INSTRUMENTS_CSV_PATH
data = pd.read_csv(instrument_csv_path)



subscribed_tokens = [256265,240641,3885825,2170625]  
token_lock = threading.Lock()  


app = Flask(__name__)

def on_ticks(ws, ticks):
    for tick in ticks:
        token = tick["instrument_token"]
        key   = f"tick:{token}"
        price = tick.get("last_price")
        ts    = tick.get("exchange_timestamp")
        ts_str = ts.isoformat() if ts else str(time.time())

        try:
            # 1) store the latest tick in a hash...
            r.hset(key, mapping={
                "price":     price,
                "timestamp": ts_str
            })
            # …and keep it around for 5 minutes
            r.expire(key, 300)

            # 2) push a realtime notification via pub/sub
            r.publish("tick_channel", json.dumps({
                "token":     token,
                "price":     price,
                "timestamp": ts_str
            }))

        except redis.exceptions.ResponseError as e:
            logger.error(f"Redis write error (skipping tick): {e}")

        logger.debug(f"TICK {token}: ₹{price}")
        

def on_connect(ws, response):
    ws.subscribe(subscribed_tokens)
    ws.set_mode(ws.MODE_FULL, subscribed_tokens)

def on_order_update(ws, data):
    logging.debug("Order update : {}".format(data))


def on_close(ws, code, reason):
    logging.info("Connection closed: {code} - {reason}".format(code=code, reason=reason))
    ws.unsubscribe(subscribed_tokens)


def on_error(ws, code, reason):
    logging.info("Connection error: {code} - {reason}".format(code=code, reason=reason))


def on_reconnect(ws, attempts_count):
    logging.info("Reconnecting: {}".format(attempts_count))

def on_noreconnect(ws):
    logging.info("Reconnect failed.")

kws.on_ticks = on_ticks
kws.on_connect = on_connect
kws.on_order_update = on_order_update
kws.on_close = on_close
kws.on_error = on_error
kws.on_connect = on_connect
kws.on_reconnect = on_reconnect
kws.on_noreconnect = on_noreconnect

def add_new_token(new_token):
    global subscribed_tokens

    with token_lock:
        if new_token not in subscribed_tokens:
            subscribed_tokens.append(new_token)
            logging.info(f"Subscribing to new token: {new_token}")
            print(f"Subscribing to new token: {new_token}")
            kws.subscribe([new_token])
            kws.set_mode(kws.MODE_FULL, [new_token])
            return True
        else:
            return False
        
        
@app.route('/ticks', methods=['POST'])
def api_register_ticks():
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
    """API to add new token dynamically."""
    data = request.get_json()

    if not data or 'token' not in data:
        return jsonify({"error": "Token is required"}), 400

    try:
        new_token = int(data['token'])
    except ValueError:
        return jsonify({"error": "Invalid token format. Must be an integer."}), 400

    if add_new_token(new_token):
        return jsonify({"message": f"Token {new_token} added successfully!"}), 200
    else:
        return jsonify({"message": f"Token {new_token} is already subscribed."}), 200

def run_flask():
    """Runs Flask app."""
    app.run(host="0.0.0.0", port=5000, debug=False)

ws_thread = threading.Thread(target=lambda: kws.connect(threaded=True), daemon=True)
ws_thread.start()


flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

while True:
    time.sleep(1)


# import time
# import threading
# import json
# import logging
# from datetime import datetime, timezone

# import redis
# from flask import Flask, request, jsonify
# from kiteconnect import KiteTicker

# from constants import (
#     ACCESS_TOKEN_PATH,
#     INSTRUMENTS_CSV_PATH,
#     SQLITE_DB_PATH,
#     TEMPLATE_FOLDER_PATH)

# with open(ACCESS_TOKEN_PATH) as f:
#     access_token = f.read().strip()

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)




# # ──────────────────────────────────────────────────────────────────────────────
# # CONFIGURATION
# # ──────────────────────────────────────────────────────────────────────────────

# API_KEY       = "zuuxkho8imp70m8c"
# ACCESS_TOKEN  = access_token

# # tokens to subscribe on connect
# TRACK_TOKENS  = {256265, 131225348, 131225604}

# # how often to emit synthetic ticks when no live data (seconds)
# SYNTHETIC_INTERVAL = 5

# # Redis connection params
# REDIS_HOST    = "127.0.0.1"
# REDIS_PORT    = 6379
# REDIS_DB      = 0

# # pub/sub channel name
# CHANNEL_NAME  = "tick_channel"

# # ──────────────────────────────────────────────────────────────────────────────
# # GLOBALS
# # ──────────────────────────────────────────────────────────────────────────────

# last_prices        = {}
# subscribed         = set()
# r                  = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# # we'll assign this once we start the WebSocket
# kws: KiteTicker = None

# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s %(levelname)s:%(name)s: %(message)s"
# )
# logger = logging.getLogger(__name__)

# app = Flask(__name__)


# # ──────────────────────────────────────────────────────────────────────────────
# # CORE PROCESSING (same as before)
# # ──────────────────────────────────────────────────────────────────────────────

# def process_tick(token: int, price: float, prev_price: float, ts_str: str, synthetic: bool=False):
#     key = f"tick:{token}"
#     try:
#         r.hset(key, mapping={
#             "price":      price,
#             "prev_price": prev_price if prev_price is not None else "",
#             "timestamp":  ts_str
#         })
#         r.expire(key, 300)

#         payload = {
#             "token":      token,
#             "price":      price,
#             "prev_price": prev_price,
#             "timestamp":  ts_str,
#             "synthetic":  synthetic
#         }
#         r.publish(CHANNEL_NAME, json.dumps(payload))

#     except redis.exceptions.RedisError as e:
#         logger.error(f"Redis write error for token {token}: {e}")

#     level = logging.INFO if synthetic else logging.DEBUG
#     logger.log(level, f"{'SYN' if synthetic else 'TICK'} {token}: ₹{price} (was ₹{prev_price})")


# def on_connect(ws, response):
#     global subscribed
#     tokens = list(TRACK_TOKENS)
#     ws.subscribe(tokens)
#     ws.set_mode(ws.MODE_FULL, tokens)
#     subscribed.update(tokens)
#     logger.info(f"Subscribed to tokens: {tokens}")


# def on_ticks(ws, ticks):
#     for tick in ticks:
#         token = tick["instrument_token"]
#         price = tick.get("last_price")
#         ts    = tick.get("exchange_timestamp")
#         ts_str = ts.isoformat() if hasattr(ts, "isoformat") else datetime.now(timezone.utc).isoformat()

#         # dynamic subscribe if new via API or external
#         if token not in subscribed:
#             ws.subscribe([token])
#             ws.set_mode(ws.MODE_FULL, [token])
#             subscribed.add(token)
#             logger.info(f"Dynamically subscribed to new token {token}")

#         prev_price = last_prices.get(token)
#         last_prices[token] = price

#         process_tick(token, price, prev_price, ts_str, synthetic=False)


# def synthetic_tick_loop():
#     while True:
#         now_str = datetime.now(timezone.utc).isoformat()
#         for token in TRACK_TOKENS:
#             redis_key = f"tick:{token}"
#             stored = r.hget(redis_key, "price")
#             price = float(stored) if stored is not None else 0.0
#             prev  = last_prices.get(token, price)
#             last_prices[token] = price
#             process_tick(token, price, prev, now_str, synthetic=True)
#         time.sleep(SYNTHETIC_INTERVAL)


# # ──────────────────────────────────────────────────────────────────────────────
# # FLASK API: subscribe / unsubscribe endpoints
# # ──────────────────────────────────────────────────────────────────────────────

# def add_new_token(token: int) -> bool:
#     """
#     Adds `token` to TRACK_TOKENS if not already present.
#     Subscribes on the WS if connected.
#     Returns True if newly added, False if it already existed.
#     """
#     if token in TRACK_TOKENS:
#         return False

#     # add to master set
#     TRACK_TOKENS.add(token)

#     # if WS is running, subscribe immediately
#     try:
#         if kws:
#             kws.subscribe([token])
#             kws.set_mode(kws.MODE_FULL, [token])
#             subscribed.add(token)
#             logger.info(f"Dynamically subscribed to new token via /ticks: {token}")
#     except Exception as e:
#         logger.error(f"Error subscribing token {token}: {e}")

#     return True

# @app.route('/ticks', methods=['POST'])
# def api_register_ticks():
#     payload = request.get_json(force=True) or {}
#     tokens  = payload.get('tokens')

#     if not isinstance(tokens, list) or not all(isinstance(t, int) for t in tokens):
#         return jsonify({"error": "`tokens` must be a list of ints"}), 400

#     results = {"subscribed": [], "skipped": []}
#     for tok in tokens:
#         if add_new_token(tok):
#             results["subscribed"].append(tok)
#         else:
#             results["skipped"].append(tok)

#     return jsonify(results), 200


# # ──────────────────────────────────────────────────────────────────────────────
# # MAIN ENTRYPOINT
# # ──────────────────────────────────────────────────────────────────────────────

# def start_kite_ws():
#     global kws
#     kws = KiteTicker(API_KEY, ACCESS_TOKEN)
#     kws.on_connect = on_connect
#     kws.on_ticks   = on_ticks
#     kws.connect(threaded=True)
#     logger.info("Kite WebSocket thread started")

# if __name__ == "__main__":
#     # start synthetic loop
#     threading.Thread(target=synthetic_tick_loop, daemon=True).start()
#     logger.info(f"Started synthetic tick loop every {SYNTHETIC_INTERVAL}s")

#     # start Kite WS
#     start_kite_ws()

#     # start Flask
#     app.run(host="0.0.0.0", port=5000)
