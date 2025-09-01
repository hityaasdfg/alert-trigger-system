#!/usr/bin/env python3
import os
import sqlite3
import time
import requests
import re

from datetime import datetime
from collections import defaultdict

from global_connection import fetch_dataframe, fetch_data, single_execute_method
from php_session_handle import STRATEGY_API_URL_EXIT


import pandas as pd 
from constants import INSTRUMENTS_CSV_PATH
from websocket_server import get_instrument_token
file_path = INSTRUMENTS_CSV_PATH
instrument_df = pd.read_csv(file_path)
 
# ─── CONFIG ────────────────────────────────────────────────────────────────
BASE_URL         = "http://192.168.4.113/khopcha/"
LOGIN_URL        = BASE_URL + "login_user.php"
EXIT_API_URL     = BASE_URL + "final_update_exit_new_v1_6.php"
TEST_SESSION_URL = BASE_URL + "testing_session.php"
SESSION_PATH     = r"\\Velocity\c\wamp64\tmp"

APACHE_USER = "khopcha"
APACHE_PASS = "qazqwe@123"

HEADERS = {
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer":          BASE_URL + "login.php",
    "Origin":           BASE_URL.rstrip('/'),
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type":     "application/x-www-form-urlencoded"
}

# maintain one session for cookies
session = requests.Session()
session.auth = (APACHE_USER, APACHE_PASS)
app_payload = {
    "username": "ALK-CNH",  
    "password": "convonix"
}


from kiteconnect import KiteConnect
access_token_path = r'\\Velocity\c\Users\kunal\Downloads\LIVE_TICK_HIGH_LOW_FLASK\LIVE_TICK_HIGH_LOW_FLASK\zerodha_access_token.txt'
access_token = open(access_token_path).read().strip()
kite = KiteConnect(api_key="zuuxkho8imp70m8c", access_token=access_token)
# ─── SESSION HELPERS ───────────────────────────────────────────────────────

def delete_session_file(php_sessid):
    """ Deletes the session file associated with the captured PHPSESSID """
    session_file = os.path.join(SESSION_PATH, f"sess_{php_sessid}")
    
    if os.path.exists(session_file):
        os.remove(session_file)
        print(f"🗑️ Deleted session file: {session_file}")
    else:
        print(f"⚠️ Session file not found: {session_file}")


# 🔹 Headers to mimic a real browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": BASE_URL + "login.php",
    "Origin": BASE_URL.rstrip('/'),
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded"
}



def login():
    """ Logs in and updates the session with a new PHPSESSID if expired """
    global session  # Ensure we're modifying the existing session

    print("🔄 Logging in...")
    login_response = session.post(LOGIN_URL, data=app_payload, headers=headers)

    if login_response.status_code != 200:
        print("❌ Login Failed! Server responded with:", login_response.status_code)
        exit()

    # 🔹 Extract PHPSESSID
    php_sessid = session.cookies.get("PHPSESSID")

    if php_sessid:
        print(f"✅ Login Successful! Captured new PHPSESSID: {php_sessid}")
        session.cookies.set("PHPSESSID", php_sessid, domain="192.168.4.113")
    else:
        print("❌ Login Failed! Could not retrieve PHPSESSID.")
        exit()




def call_api(api_url, retry=True):
    """ Function to make API requests using the active session. If expired, re-login and retry once. """
    response = session.get(api_url, headers=headers)
    
    if response.status_code == 401:  # Unauthorized -> session expired
        print("⚠️ Unauthorized! Session expired.")
        
        if retry:  # Retry login only once to avoid infinite loops
            print("🔄 Re-logging in and retrying request...")
            login()
            return call_api(api_url, retry=False)  # Retry only once
        
        print("❌ Session expired and re-login failed. Exiting.")
        exit()

    return response.text


def call_php_exit_db_api(payload,retry=True):
    """ Sends an API request using session authentication. """

    # 🔹 Secure Basic Authorization for API requests
    # basic_auth_token = base64.b64encode(f"{apache_username}:{apache_password}".encode()).decode()

    # 🔹 Headers (Dynamically generated)
    

    # 🔹 Send request using session
    response = session.post(STRATEGY_API_URL_EXIT, headers=headers, data=payload)
    # live_scanner_id = response.json()
    print (response.text)
    # single_execute_method(f"UPDATE `alerts_rows` SET `live_scanner_id` = `{int(live_scanner_id)}` WHERE `id` = {id};")
    # 🔹 Handle Session Expiry
    if response.status_code == 401:  # Unauthorized - session expired
        print("⚠️ Unauthorized! Session expired during API call.")
        print("🔄 Attempting to re-login...")

        if retry:  # Retry login only once to avoid infinite loops
            print("🔄 Re-logging in and retrying request...")
            login()
            return call_php_exit_db_api(payload,retry=False)  # Retry only once

    return response.text
def clean_symbol(symbol):
    pattern = r"^([A-Z0-9]+?)(\d+)(CE|PE)$"
    match = re.match(pattern, symbol)
    if match:
        script = match.group(1)
        strike_price = match.group(2)
        option_type = match.group(3)
        return script, strike_price, option_type
    else:
        return None, None, None

def calculate_margin(symbol, price, qty, trade_type):
    """Calculate margin for an options contract based on trade type."""
    if not symbol or not qty or not trade_type:
        return {'error': 'Missing required fields'}
    
    try:
        qty_int = int(qty)
    except ValueError:
        return {'error': 'Quantity must be an integer'}
    
    if trade_type == 'B':  # Buying requires upfront margin
        if price is None:
            return {'error': 'Price is required for buy trades'}
        return {'margin': float(price) * qty_int}
    
    elif trade_type == 'S':  # Selling requires margin calculation
        script, strike_price, option_type = clean_symbol(symbol)
        if not script or not strike_price or not option_type:
            return {'error': 'Invalid symbol format'}
        
        url = "https://zerodha.com/margin-calculator/SPAN"
        payload = {
            "action": "calculate",
            "exchange[]": "NFO",
            "product[]": "OPT",
            "scrip[]": script,
            "option_type[]": option_type,
            "strike_price[]": strike_price,
            "qty[]": qty_int,
            "trade[]": "sell"
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': 'Mozilla/5.0'
        }
        
        try:
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            result = response.json().get('total', {}).get('total', 0)
            return {'margin': result}
        except Exception as e:
            return {'error': str(e)}
    
    return {'error': 'Invalid trade type'}

def fetch_currunt_price(symbol: str) -> float:
    """
    Fetch the latest last_price for the given symbol via Kite Connect.
    Handles common index aliases automatically.
    Returns None if the fetch fails or the symbol isn’t found.
    """
    # 1) Normalize & map any special cases
    alias_map = {
        "NIFTY":     "NIFTY 50",
        "BANKNIFTY": "NIFTY BANK",
        "SENSEX":    "SENSEX",
    }
    resolved = alias_map.get(symbol.strip().upper(), symbol.strip().upper())

    # 2) Build the instrument key
    exchange   = "NSE"
    instrument = f"{exchange}:{resolved}"

    # 3) Fetch LTP
    try:
        ltp_data = kite.ltp(instrument)
        return ltp_data[instrument]["last_price"]
    except KeyError:
        print(f"Instrument {instrument} not found in response.")
    except Exception as e:
        print(f"Error fetching price for {instrument}: {e}")
    return None


# if __name__ == "__main__":
#     for sym in ["NIFTY", "BANKNIFTY", "SENSEX", "RELIANCE"]:
#         price = fetch_currunt_price(sym)
#         print(f"{sym:10} → {price}")
# exit(0)

 
def create_exit_payload(trade_data, exit_prices, exit_lots, exit_date):
    """Generate payload for full exit, handling all strategies with complete field set."""
    if isinstance(trade_data, list):
        if not trade_data:
            raise ValueError("No trade data to exit")
        trade = trade_data[0]
    elif isinstance(trade_data, dict):
        trade = trade_data
    else:
        raise TypeError("trade_data must be a dict or non-empty list of dicts")
    
    print(exit_prices, exit_lots, exit_date)
    
    # Validate trade legs
    future_lots = abs(trade.get('future_no_of_lots', 0) or 0)
    option_lots = abs(trade.get('ce_no_of_lots_1') or trade.get('pe_no_of_lots_1') or 0)
    
    if exit_lots.get('future', 0) > future_lots:
        exit_lots['future'] = future_lots
    if exit_lots.get('option', 0) > option_lots:
        exit_lots['option'] = option_lots

    # Calculate new margin after exit
    new_margin_data = {'margin': 0}
    new_margin = new_margin_data.get('margin', trade.get('margin', 0))

    # Base payload with all required fields
    payload = {
        'id': trade['id'],
        'strategy_name': trade['strategy_name'],
        'cmp_at_exit': fetch_currunt_price(str(trade['underlying'])),
        'underlying': trade['underlying'],
        'lot_size': trade['lot_size'],
        'entry_date': trade['entry_date'].strftime('%Y-%m-%d %H:%M:%S'),
        'expiry_date': trade['expiry_date'].strftime('%Y-%m-%d'),
        'realised_profit_loss': trade.get('realised_profit_loss', 0),
        'max_of_max_profit': trade.get('max_of_max_profit', None),
        'max_of_max_loss': trade.get('max_of_max_loss', None),
        'margin': trade.get('margin', 0),
        'margin_to_update': new_margin,
        'exit_date': exit_date,
        'exit_full_strategy_flag': 1,
        'status': 'exit',
        
        # Call Option 1 fields (always present)
        'ce_strike_price_1': None,
        'ce_entry_price_1': None,
        'ce_price_to_update_1': None,
        'ce_no_of_lots_1': None,
        'ce_no_of_lots_to_update_1': None,
        'max_of_ce_no_of_lots_1': 0,
        'is_ce_1_add': 0,
        'is_ce_1_remove': 0,
        'is_ce_1_long': 1,
        'ce_margin_1': None,
        'ce_margin_to_update_1': None,
        
        # Put Option 1 fields (always present)
        'pe_strike_price_1': None,
        'pe_entry_price_1': None,
        'pe_price_to_update_1': None,
        'pe_no_of_lots_1': None,
        'pe_no_of_lots_to_update_1': None,
        'max_of_pe_no_of_lots_1': 0,
        'is_pe_1_add': 0,
        'is_pe_1_remove': 0,
        'is_pe_1_long': 1,
        'pe_margin_1': None,
        'pe_margin_to_update_1': None,
        
        # Call Option 2 fields (always present)
        'ce_strike_price_2': None,
        'ce_entry_price_2': None,
        'ce_price_to_update_2': None,
        'ce_no_of_lots_2': None,
        'ce_no_of_lots_to_update_2': None,
        'max_of_ce_no_of_lots_2': 0,
        'is_ce_2_add': 0,
        'is_ce_2_remove': 0,
        'is_ce_2_long': 1,
        'ce_margin_2': None,
        'ce_margin_to_update_2': None,
        
        # Put Option 2 fields (always present)
        'pe_strike_price_2': None,
        'pe_entry_price_2': None,
        'pe_price_to_update_2': None,
        'pe_no_of_lots_2': None,
        'pe_no_of_lots_to_update_2': None,
        'max_of_pe_no_of_lots_2': 0,
        'is_pe_2_add': 0,
        'is_pe_2_remove': 0,
        'is_pe_2_long': 1,
        'pe_margin_2': None,
        'pe_margin_to_update_2': None,
        
        # Future fields (always present)
        'future_entry_price': None,
        'future_price_to_update': None,
        'future_no_of_lots': None,
        'future_no_of_lots_to_update': None,
        'max_of_future_no_of_lots': 0,
        'is_future_add': 0,
        'is_future_remove': 0,
        'is_future_long': 1,
        'future_margin': None,
        'future_margin_to_update': None
    }

    strategy = trade['strategy_name'].lower().replace(' ', '_')
    
    if strategy == 'covered_call':
        # Update Future leg
        payload.update({
            'future_entry_price': trade.get('future_entry_price'),
            'future_price_to_update': exit_prices.get('future'),
            'future_no_of_lots': future_lots,
            'future_no_of_lots_to_update': exit_lots.get('future'),
            'is_future_remove': 1,
            'is_future_long': 1,  # Long future position
            'future_margin': trade.get('future_margin'),
            'future_margin_to_update': new_margin,
        })
        
        # Update Call Option leg
        payload.update({
            'ce_strike_price_1': trade.get('ce_strike_price_1'),
            'ce_entry_price_1': trade.get('ce_entry_price_1'),
            'ce_price_to_update_1': exit_prices.get('option'),
            'ce_no_of_lots_1': abs(option_lots),
            'ce_no_of_lots_to_update_1': exit_lots.get('option'),
            'is_ce_1_remove': 1,
            'is_ce_1_long': 0,  # Short call in covered call
            'ce_margin_1': trade.get('ce_margin_1'),
            'ce_margin_to_update_1': new_margin,
        })
    
    elif strategy == 'covered_put':
        # Update Future leg
        payload.update({
            'future_entry_price': trade.get('future_entry_price'),
            'future_price_to_update': exit_prices.get('future'),
            'future_no_of_lots': future_lots,
            'future_no_of_lots_to_update': exit_lots.get('future'),
            'is_future_remove': 1,
            'is_future_long': 0,  # Short future position
            'future_margin': trade.get('future_margin'),
            'future_margin_to_update': new_margin,
        })
        
        # Update Put Option leg
        payload.update({
            'pe_strike_price_1': trade.get('pe_strike_price_1'),
            'pe_entry_price_1': trade.get('pe_entry_price_1'),
            'pe_price_to_update_1': exit_prices.get('option'),
            'pe_no_of_lots_1': abs(option_lots),
            'pe_no_of_lots_to_update_1': exit_lots.get('option'),
            'is_pe_1_remove': 1,
            'is_pe_1_long': 0,  # Short put in covered put
            'pe_margin_1': trade.get('pe_margin_1'),
            'pe_margin_to_update_1': new_margin,
        })
        
    elif strategy in ['long_call', 'short_call']:
        is_long = 1 if strategy == 'long_call' else 0
        payload.update({
            'ce_strike_price_1': trade.get('ce_strike_price_1'),
            'ce_entry_price_1': trade.get('ce_entry_price_1'),
            'ce_price_to_update_1': exit_prices.get('option'),
            'ce_no_of_lots_1': abs(trade.get('ce_no_of_lots_1')),
            'ce_no_of_lots_to_update_1': exit_lots.get('option'),
            'is_ce_1_remove': 1,
            'is_ce_1_long': is_long,
            'ce_margin_1': trade.get('ce_margin_1'),
            'ce_margin_to_update_1': new_margin,
        })

    elif strategy in ['long_put', 'short_put']:
        is_long = 1 if strategy == 'long_put' else 0
        payload.update({
            'pe_strike_price_1': trade.get('pe_strike_price_1'),
            'pe_entry_price_1': trade.get('pe_entry_price_1'),
            'pe_price_to_update_1': exit_prices.get('option'),
            'pe_no_of_lots_1': abs(trade.get('pe_no_of_lots_1')),
            'pe_no_of_lots_to_update_1': exit_lots.get('option'),
            'is_pe_1_remove': 1,
            'is_pe_1_long': is_long,
            'pe_margin_1': trade.get('pe_margin_1'),
            'pe_margin_to_update_1': new_margin,
        })
        
    elif strategy == 'bearish_debit_spread':
        # Put spread – use two put legs
        payload.update({
            'pe_strike_price_1': trade.get('pe_strike_price_1'),
            'pe_entry_price_1': trade.get('pe_entry_price_1'),
            'pe_price_to_update_1': exit_prices.get('option_1'),
            'pe_no_of_lots_1': abs(trade.get('pe_no_of_lots_1')),
            'pe_no_of_lots_to_update_1': abs(exit_lots.get('option_1')),
            'max_of_pe_no_of_lots_1': trade.get('max_of_pe_no_of_lots_1', 0),
            'is_pe_1_remove': 1,
            'is_pe_1_long': 1,  # Buy lower strike PUT
            'pe_margin_1': trade.get('pe_margin_1'),
            'pe_margin_to_update_1': new_margin,

            'pe_strike_price_2': trade.get('pe_strike_price_2'),
            'pe_entry_price_2': trade.get('pe_entry_price_2'),
            'pe_price_to_update_2': exit_prices.get('option_2'),
            'pe_no_of_lots_2': abs(trade.get('pe_no_of_lots_2')),
            'pe_no_of_lots_to_update_2': abs(exit_lots.get('option_2')),
            'max_of_pe_no_of_lots_2': trade.get('max_of_pe_no_of_lots_2', 0),
            'is_pe_2_remove': 1,
            'is_pe_2_long': 0,  # Sell higher strike PUT
            'pe_margin_2': trade.get('pe_margin_2'),
            'pe_margin_to_update_2': new_margin,
        })
        
    elif strategy == 'bearish_credit_spread':
        payload.update({
            'ce_strike_price_1': trade.get('ce_strike_price_1'),
            'ce_entry_price_1': trade.get('ce_entry_price_1'),
            'ce_price_to_update_1': exit_prices.get('option_1'),
            'ce_no_of_lots_1': abs(trade.get('ce_no_of_lots_1')),
            'ce_no_of_lots_to_update_1': abs(exit_lots.get('option_1')),
            'max_of_ce_no_of_lots_1': trade.get('max_of_ce_no_of_lots_1', 0),
            'is_ce_1_remove': 1,
            'is_ce_1_long': 0,  # Sell ITM Call
            'ce_margin_1': trade.get('ce_margin_1'),
            'ce_margin_to_update_1': new_margin,

            'ce_strike_price_2': trade.get('ce_strike_price_2'),
            'ce_entry_price_2': trade.get('ce_entry_price_2'),
            'ce_price_to_update_2': exit_prices.get('option_2'),
            'ce_no_of_lots_2': abs(trade.get('ce_no_of_lots_2')),
            'ce_no_of_lots_to_update_2': abs(exit_lots.get('option_2')),
            'max_of_ce_no_of_lots_2': trade.get('max_of_ce_no_of_lots_2', 0),
            'is_ce_2_remove': 1,
            'is_ce_2_long': 1,  # Buy OTM Call
            'ce_margin_2': trade.get('ce_margin_2'),
            'ce_margin_to_update_2': new_margin
        })
    
    elif strategy == 'bullish_credit_spread':
        payload.update({
            'pe_strike_price_1': trade.get('pe_strike_price_1'),
            'pe_entry_price_1': trade.get('pe_entry_price_1'),
            'pe_price_to_update_1': exit_prices.get('option_1'),
            'pe_no_of_lots_1': abs(trade.get('pe_no_of_lots_1')),
            'pe_no_of_lots_to_update_1': abs(exit_lots.get('option_1')),
            'max_of_pe_no_of_lots_1': trade.get('max_of_pe_no_of_lots_1', 0),
            'is_pe_1_remove': 1,
            'is_pe_1_long': 0,  # Sell ITM Put
            'pe_margin_1': trade.get('pe_margin_1'),
            'pe_margin_to_update_1': new_margin,

            'pe_strike_price_2': trade.get('pe_strike_price_2'),
            'pe_entry_price_2': trade.get('pe_entry_price_2'),
            'pe_price_to_update_2': exit_prices.get('option_2'),
            'pe_no_of_lots_2': abs(trade.get('pe_no_of_lots_2')),
            'pe_no_of_lots_to_update_2': abs(exit_lots.get('option_2')),
            'max_of_pe_no_of_lots_2': trade.get('max_of_pe_no_of_lots_2', 0),
            'is_pe_2_remove': 1,
            'is_pe_2_long': 1,  # Buy OTM Put
            'pe_margin_2': trade.get('pe_margin_2'),
            'pe_margin_to_update_2': new_margin
        })
    
    elif strategy == 'bullish_debit_spread':
        payload.update({
            'ce_strike_price_1': trade.get('ce_strike_price_1'),
            'ce_entry_price_1': trade.get('ce_entry_price_1'),
            'ce_price_to_update_1': exit_prices.get('option_1'),
            'ce_no_of_lots_1': abs(trade.get('ce_no_of_lots_1')),
            'ce_no_of_lots_to_update_1': abs(exit_lots.get('option_1')),
            'max_of_ce_no_of_lots_1': trade.get('max_of_ce_no_of_lots_1', 0),
            'is_ce_1_remove': 1,
            'is_ce_1_long': 1,  # Buy ITM Call
            'ce_margin_1': trade.get('ce_margin_1'),
            'ce_margin_to_update_1': new_margin,

            'ce_strike_price_2': trade.get('ce_strike_price_2'),
            'ce_entry_price_2': trade.get('ce_entry_price_2'),
            'ce_price_to_update_2': exit_prices.get('option_2'),
            'ce_no_of_lots_2': abs(trade.get('ce_no_of_lots_2')),
            'ce_no_of_lots_to_update_2': abs(exit_lots.get('option_2')),
            'max_of_ce_no_of_lots_2': trade.get('max_of_ce_no_of_lots_2', 0),
            'is_ce_2_remove': 1,
            'is_ce_2_long': 0,  # Sell OTM Call
            'ce_margin_2': trade.get('ce_margin_2'),
            'ce_margin_to_update_2': new_margin
        })
    
    elif strategy == 'long_future':
        payload.update({
            'future_entry_price': trade.get('future_entry_price'),
            'future_price_to_update': exit_prices.get('future'),
            'future_no_of_lots': abs(trade.get('future_no_of_lots')),
            'future_no_of_lots_to_update': abs(exit_lots.get('future')),
            'max_of_future_no_of_lots': trade.get('max_of_future_no_of_lots', 0),
            'is_future_remove': 1,
            'is_future_long': 1,
            'future_margin': trade.get('future_margin'),
            'future_margin_to_update': new_margin
        })
    
    elif strategy == 'short_future':
        payload.update({
            'future_entry_price': trade.get('future_entry_price'),
            'future_price_to_update': exit_prices.get('future'),
            'future_no_of_lots': abs(trade.get('future_no_of_lots')),
            'future_no_of_lots_to_update': abs(exit_lots.get('future')),
            'max_of_future_no_of_lots': trade.get('max_of_future_no_of_lots', 0),
            'is_future_remove': 1,
            'is_future_long': 0,
            'future_margin': trade.get('future_margin'),
            'future_margin_to_update': new_margin
        })
    
    elif strategy == 'short_strangle':
        payload.update({
            'ce_strike_price_1': trade.get('ce_strike_price_1'),
            'ce_entry_price_1': trade.get('ce_entry_price_1'),
            'ce_price_to_update_1': exit_prices.get('option_1'),
            'ce_no_of_lots_1': abs(trade.get('ce_no_of_lots_1')),
            'ce_no_of_lots_to_update_1': abs(exit_lots.get('option_1')),
            'max_of_ce_no_of_lots_1': trade.get('max_of_ce_no_of_lots_1', 0),
            'is_ce_1_remove': 1,
            'is_ce_1_long': 0,  # Sell Call
            'ce_margin_1': trade.get('ce_margin_1'),
            'ce_margin_to_update_1': new_margin,

            'pe_strike_price_1': trade.get('pe_strike_price_1'),
            'pe_entry_price_1': trade.get('pe_entry_price_1'),
            'pe_price_to_update_1': exit_prices.get('option_2'),
            'pe_no_of_lots_1': abs(trade.get('pe_no_of_lots_1')),
            'pe_no_of_lots_to_update_1': abs(exit_lots.get('option_2')),
            'max_of_pe_no_of_lots_1': trade.get('max_of_pe_no_of_lots_1', 0),
            'is_pe_1_remove': 1,
            'is_pe_1_long': 0,  # Sell Put
            'pe_margin_1': trade.get('pe_margin_1'),
            'pe_margin_to_update_1': new_margin
        })
    
    # print(payload)

    return payload
    

def exit_trade_fr_ls(trade_id, exit_prices, exit_lots, symbol,user_id):
    """Fetch trade details and exit both legs of the trade with different prices and lots, ensuring full removal."""
    # user_id = "6107a84358676f862be226daae343418"
    # print (f"SELECT * FROM live_strategies_evaluation WHERE user_id = '{user_id}' AND id = {int(trade_id)} ORDER BY id DESC")
    data = fetch_dataframe(f"SELECT * FROM live_strategies_evaluation WHERE user_id = '{user_id}' AND id = {int(trade_id)} ORDER BY id DESC")
    # print (data['actual_profit_loss'])
    trade_data = data.to_dict('records')
    # print (trade_data)
    if not trade_data:
        print("Trade ID not found.")
        return

    exit_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    exit_payload = create_exit_payload(trade_data, exit_prices, exit_lots, exit_date)
    
    # print("Sending exit payload:", exit_payload)
    exit_in_live_scanner(exit_payload)
    return  # ✅ Ensure the function exits

def exit_in_live_scanner(payload):

    login()

    # 🔹 Step 2: Call API with session sess_bbdd69otc2sat9eu2bnbt5nb9u
    print("\n📄 API Response for TEST_SESSION_URL:")
    print(call_api(TEST_SESSION_URL))
    # print(strategy,data)
    call_php_exit_db_api(payload)

    time.sleep(1)
    php_sessid = session.cookies.get("PHPSESSID")
    # print (php_sessid)
    delete_session_file(php_sessid)

def process_exit(orders_data,user_key):
    """Processes exit conditions for grouped trades."""
    if not orders_data:
        return None

    trade_id = orders_data[0]['trade_id']
    has_future = False
    exit_prices = {}
    exit_lots = {}
    option_orders = []

    for order in orders_data:
        symbol = order['tradingsymbol']
        if "FUT" in symbol.upper():
            has_future = True
            exit_prices['future'] = order['limit_price']
            exit_lots['future'] = order['lots']
        else:
            option_orders.append(order)

    if option_orders:
        if len(option_orders) == 1:
            op = option_orders[0]
            exit_prices['option'] = op['limit_price']
            exit_lots['option'] = op['lots']
        else:
            for idx, op in enumerate(option_orders, start=1):
                key = f'option_{idx}'
                exit_prices[key] = op['limit_price']
                exit_lots[key] = op['lots']

    final_symbol = '' if has_future else orders_data[0]['tradingsymbol']
    exit_trade_fr_ls(trade_id, exit_prices, exit_lots, final_symbol,user_key)


def verify_trades_data(orders_data,user_key):
    """Groups orders, updates trade_id from DB, and processes exit conditions."""
    trade_groups = defaultdict(list)

    for order in orders_data:
        key = (order['trade_id'], order['tradingsymbol'])
        trade_groups[key].append(order)

    after_group_by = list(trade_groups.values())
    for trade_group in after_group_by:
        process_exit(trade_group,user_key)



def send_full_exit(instrument, scanner_id, exit_price, exit_quantity, user_id):
    exit_date = datetime.now().strftime('%Y-%m-%d')
    print("→", instrument, scanner_id, exit_price, exit_quantity, exit_date, user_id)

    # Get previous day's last NIFTY price
    get_nifty_data_q = fetch_data("SELECT price FROM live_tick_nifty  ORDER BY time DESC LIMIT 1;")
    if not get_nifty_data_q:
        print("❌ No NIFTY data found for previous day.")
        return

    Nifty_on_Sell = str(get_nifty_data_q[0][0])
    print("📊 Nifty on Sell:", Nifty_on_Sell)

    # Get symbol trade details
    symbol_values = fetch_data(f"""
        SELECT `Symbol Name`, `Quantity`, `Price`, `Date`, `Nifty vs Stock`, `Nifty on Buy`
        FROM eq_scanner
        WHERE `id` = {scanner_id}
          AND `userid` = '{user_id}'
          AND `Sell Condition` IS NULL;
    """)

    if not symbol_values:
        print("❌ No matching scanner entry found.")
        return

    try:
        entry_price = float(symbol_values[0][2])
        quantity = int(symbol_values[0][1])
        margin_used = round(entry_price * int(exit_quantity), 2)

        # P&L Calculation
        book_profit = round((float(exit_price) - entry_price) * quantity, 2)

        # Validate Nifty on Buy
        nifty_on_buy_raw = symbol_values[0][5]
        try:
            nifty_on_buy = float(nifty_on_buy_raw)
            if nifty_on_buy == 0:
                raise ValueError
        except (ValueError, TypeError):
            print(f"⚠️ Invalid Nifty on Buy: {nifty_on_buy_raw}")
            nifty_on_buy = None

        # Calculate Nifty profit if valid
        if nifty_on_buy:
            nifty_profit = (margin_used / nifty_on_buy) * (float(Nifty_on_Sell) - nifty_on_buy)
            nifty_vs_stock = book_profit - nifty_profit
            nvs = round(nifty_vs_stock, 2)
            nifty_mtm = round(nifty_profit, 2)
        else:
            nifty_mtm = 0
            nvs = 0

        # Update the record
        update_query = (
            f"UPDATE `eq_scanner` SET `Sell Date`='{exit_date}', `Sell Condition`='stop loss hit', "
            f"`Booked Profit`='{book_profit}', `Nifty on Sell`='{Nifty_on_Sell}', `Exit_price`='{exit_price}', "
            f"`nifty mtm`='{nifty_mtm}', `Adj Exit`={float(exit_price)}, `Nifty vs Stock`={nvs} "
            f"WHERE `id`={scanner_id} AND `userid`='{user_id}' AND `partial`=0;"
        )
        single_execute_method(update_query)
        print("✅ Exit updated successfully.")

    except Exception as e:
        print("❌ Error during exit processing:", e)
        
