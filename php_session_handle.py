import requests
from requests.auth import HTTPBasicAuth
import os
import time
import base64
from datetime import datetime
# from global_connection import single_execute_method

# 🔹 Define URLs
BASE_URL = "http://192.168.4.113/khopcha/"
LOGIN_URL = BASE_URL + "login_user.php"   # Login API
# STRATEGY_API_URL = BASE_URL + "add_strategy_to_db_server_v1_6.php"  # Strategy API
STRATEGY_API_URL = BASE_URL + "testing_insert_script.php"
STRATEGY_API_URL_EXIT = BASE_URL + "final_update_exit_new_v1_6.php"
TEST_SESSION_URL = BASE_URL + "testing_session.php"  # Session verification API

# 🔹 Apache Credentials (if required)
apache_username = "khopcha"
apache_password = "qazqwe@123"

# 🔹 User Login Credentials
app_payload = {
    "username": "ALK-CNH",  
    "password": "convonix"
}

'''

def insert_eq_scanner_entries(eq_orders_data):
    currundate = datetime.now().date()
    entry = "entry"
    nifty_on_buy = fetch_data("SELECT price FROM live_tick_nifty ORDER BY time DESC LIMIT 1;")[0][0]
    instrument = eq_orders_data[0]
    qty = eq_orders_data[1]
    price = eq_orders_data[2]
    target = ''
    stop_loss = ''
    user_id = eq_orders_data[3]

    insert_q = f"""
    INSERT INTO eq_scanner 
    (`Symbol Name`, `Quantity`, `Price`, `Date`, `Buy Condition`, `nifty on buy`, `target`, `stop_loss`, `userid`) 
    VALUES 
    ('{instrument}', '{qty}', '{price}', '{currundate}', '{entry}', '{nifty_on_buy}', '{target}', '{stop_loss}', '{user_id}')
    """
    single_execute_method(insert_q)

'''

session_path = r"\\Velocity\c\wamp64\tmp"

def delete_session_file(php_sessid):
    """ Deletes the session file associated with the captured PHPSESSID """
    session_file = os.path.join(session_path, f"sess_{php_sessid}")
    
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

# 🔹 Start a session to maintain cookies
session = requests.Session()
session.auth = HTTPBasicAuth(apache_username, apache_password)

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

def call_php_insert_db_api(id,payload,retry=True):
    """ Sends an API request using session authentication. """

    # 🔹 Secure Basic Authorization for API requests
    # basic_auth_token = base64.b64encode(f"{apache_username}:{apache_password}".encode()).decode()

    # 🔹 Headers (Dynamically generated)
    instruments_in  = tuple(payload['instruments'])
    if len(instruments_in) == 1:
        instruments_in = f"('{instruments_in[0]}')"
    else:
        instruments_in = instruments_in
    
    payload.pop('instruments')

    # 🔹 Send request using session
    response = session.post(STRATEGY_API_URL, headers=headers, data=payload)
    live_scanner_id = response.json()
    # # print (f"UPDATE `alerts_rows` SET `live_scanner_id` = {int(live_scanner_id)} WHERE `id` = {id};")
    # single_execute_method(f"UPDATE `alerts_rows` SET `live_scanner_id` = {int(live_scanner_id)} WHERE `id` = {id};")
    # # print (f"UPDATE `alert_conditions_rows` SET `per_trade_id` = {int(live_scanner_id)} WHERE `alert_id` = {id} and instrument in {instruments_in};")
    # single_execute_method(f"UPDATE `alert_conditions_rows` SET `per_trade_id` = {int(live_scanner_id)} WHERE `alert_id` = {id} and instrument in {instruments_in};")
    # 🔹 Handle Session Expiry
    if response.status_code == 401:  # Unauthorized - session expired
        print("Unauthorized! Session expired during API call.")
        print("Attempting to re-login...")

        if retry:  # Retry login only once to avoid infinite loops
            print("Re-logging in and retrying request...")
            login()
            return call_php_insert_db_api(payload,retry=False)  # Retry only once

    return response.text

def generate_strategy_payload(id,strategy_name, data,user_id):
    """ Generates the correct payload dynamically for each strategy """

    # Extract expiry date from the first leg dynamically
    expiry_date = data[0].get("expiry")
    payload = {
        "user_id": user_id,
        "underlying": data[0].get("name"),
        "account_name": "python_api",
        "entry_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "underlying_cmp": data[0].get("price", 0),
        "lot_size": data[0].get("lots"),
        "expiry_date": expiry_date,
        "strategy_name": strategy_name,
        "margin": max(item.get("margin", 0) for item in data),  # Max Margin
        "ivp": 60.1,
        "instruments" : [item['instrument'] for item in data]
    }

    # Strategy Mapping
    strategies = {
        "long_call": [("B", "CE")],
        "short_call": [("S", "CE")],
        "long_put": [("B", "PE")],
        "short_put": [("S", "PE")],
        "bullish_credit_spread": [("S", "PE"), ("B", "PE")],
        "bearish_credit_spread": [("S", "CE"), ("B", "CE")],
        "bullish_debit_spread": [("B", "CE"), ("S", "CE")],
        "bearish_debit_spread": [("B", "PE"), ("S", "PE")],
        "covered_call": [("B", "FUT"), ("S", "CE")],
        "covered_put": [("S", "FUT"), ("B", "PE")],
        "iron_condor": [("S", "CE"), ("B", "CE"), ("S", "PE"), ("B", "PE")],  # Fix order
        "short_strangle": [("S", "CE"), ("S", "PE")],
        "long_collar": [("B", "FUT"), ("S", "PE")],
        "long_future": [("B", "FUT")],
        "short_future": [("S", "FUT")]
    }

    # **Fix for Iron Condor**
    if strategy_name == "iron_condor":
        ce_legs = sorted([leg for leg in data if leg["option_type"] == "CE"], key=lambda x: x["strike_price"])
        pe_legs = sorted([leg for leg in data if leg["option_type"] == "PE"], key=lambda x: x["strike_price"], reverse=True)

        # Assign Correct Order:
        iron_condor_data = [
            ("S", "CE", ce_legs[0]),  # Sell lower CE
            ("B", "CE", ce_legs[1]),  # Buy higher CE
            ("S", "PE", pe_legs[0]),  # Sell higher PE
            ("B", "PE", pe_legs[1])   # Buy lower PE
        ]
    else:
        iron_condor_data = [(trade_type, option_type, data[i]) for i, (trade_type, option_type) in enumerate(strategies[strategy_name])]

    # Iterate over expected strategy legs
    for i, (trade_type, option_type, leg) in enumerate(iron_condor_data, start=1):
        strike_price = leg.get("strike")
        entry_price = leg.get("price")
        qty = leg.get("qty")
        order_type = "sell" if trade_type == "S" else "buy"
        if option_type == "CE":
            payload.update({
                f"ce_strike_price_{i}": strike_price,
                f"ce_entry_price_{i}": entry_price,
                f"ce_no_of_lots_{i}": qty,
                f"is_ce_{i}_long": order_type
            })
        elif option_type == "PE":
            payload.update({
                f"pe_strike_price_{i}": strike_price,
                f"pe_entry_price_{i}": entry_price,
                f"pe_no_of_lots_{i}": qty,
                f"is_pe_{i}_long": order_type
            })
        elif option_type == "FUT":
            payload.update({
                "future_entry_price": entry_price,
                "future_no_of_lots": qty,
                "is_future_long": order_type
            })
    # print (payload)
    call_php_insert_db_api(id,payload)
    return payload

# 🔹 Step 1: Login initially
def enter_in_live_scanner(id,strategy,data,user_id):

    login()

    # 🔹 Step 2: Call API with session sess_bbdd69otc2sat9eu2bnbt5nb9u
    print("\n📄 API Response for TEST_SESSION_URL:")
    print(call_api(TEST_SESSION_URL))
    print(strategy,data)
    generate_strategy_payload(id,strategy,data,user_id)

    time.sleep(1)
    php_sessid = session.cookies.get("PHPSESSID")
    # print (php_sessid)
    delete_session_file(php_sessid)
    
    
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




# id  = 111
# strategy = "bullish_credit_spread" 
# data = [{'id': 111, 'alert_id': 119, 'type': 'B', 'instrument': 'NIFTY25FEB22500PE', 'ltp': 37.2, 'qty': 10, 'price': 35.25, 'margin': 26437.5, 'lots': 75, 'per_trade_id': None, 'name': 'NIFTY', 'expiry': '2025-02-27', 'strike': 22500.0, 'instrument_type': 'PE', 'exchange': 'NFO'}, {'id': 112, 'alert_id': 119, 'type': 'S', 'instrument': 'NIFTY25FEB22600PE', 'ltp': 72.8, 'qty': 10, 'price': 69.85, 'margin': 1902572.25, 'lots': 75, 'per_trade_id': None, 'name': 'NIFTY', 'expiry': '2025-02-27', 'strike': 22600.0, 'instrument_type': 'PE', 'exchange': 'NFO'}]


# enter_in_live_scanner(id,strategy,data,'3b8c0793f04043ff2e2ba695c69f11ab')