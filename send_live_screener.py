import sqlite3
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import os
# from main_app import get_lot_size
from global_connection import fetch_data,query_execute_method
# === PHP API Details ===


import pandas as pd 
from constants import INSTRUMENTS_CSV_PATH



file_path = INSTRUMENTS_CSV_PATH
instrument_df = pd.read_csv(file_path)


BASE_URL = "http://192.168.4.113/khopcha/"
LOGIN_URL = BASE_URL + "login_user.php"
STRATEGY_API_URL = BASE_URL + "testing_insert_script.php"
session_path = r"\\Velocity\c\wamp64\tmp"

apache_username = "khopcha"
apache_password = "qazqwe@123"

app_payload = {
    "username": "ALK-CNH",
    "password": "convonix"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": BASE_URL + "login.php",
    "Origin": BASE_URL.rstrip('/'),
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded"
}

session = requests.Session()
session.auth = HTTPBasicAuth(apache_username, apache_password)


def login():
    print("🔄 Logging in...")
    response = session.post(LOGIN_URL, data=app_payload, headers=headers)
    if response.status_code != 200:
        raise Exception("Login failed with status code", response.status_code)

    php_sessid = session.cookies.get("PHPSESSID")
    if php_sessid:
        print(f"✅ Logged in. PHPSESSID: {php_sessid}")
        session.cookies.set("PHPSESSID", php_sessid, domain="192.168.4.113")
    else:
        raise Exception("Login failed. PHPSESSID not retrieved.")


def call_php_insert_db_api(alert_id, payload, retry=True):
    instruments_in = tuple(payload.get('instruments', []))
    if len(instruments_in) == 1:
        instruments_in = f"('{instruments_in[0]}')"
    payload.pop('instruments', None)

    response = session.post(STRATEGY_API_URL, headers=headers, data=payload)

    if response.status_code == 401 and retry:
        print("⚠️ Session expired. Retrying login...")
        login()
        return call_php_insert_db_api(alert_id, payload, retry=False)

    try:
        live_scanner_id = int(response.json())
        print("✅ API Response:", live_scanner_id)
        db_path = r"C:\Users\Alkalyme\Downloads\ato_project\ato_project\instance\ato_system.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET live_scanner_id = ? WHERE id = ?", (live_scanner_id, alert_id))
        cursor.execute("UPDATE baskets SET live_scanner_id = ? WHERE alert_id = ?", (live_scanner_id, alert_id))
        conn.commit()
        conn.close()

        print(f"✅ Stored live_scanner_id={live_scanner_id} in alerts and baskets tables.")
        return live_scanner_id

    except Exception as e:
        print("⚠️ Error saving or parsing response:", e)
        print("⚠️ Raw response:", response.text)
        return response.text



def generate_strategy_payload(alert_id, strategy_name, data, user_id):
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
        "margin": max(item.get("margin", 0) for item in data),
        "ivp": 60.1,
        "instruments": [item['instrument'] for item in data]
    }

    # Strategy leg templates
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
        "iron_condor": [("S", "CE"), ("B", "CE"), ("S", "PE"), ("B", "PE")],
        "short_strangle": [("S", "CE"), ("S", "PE")],
        "long_collar": [("B", "FUT"), ("S", "PE")],
        "long_future": [("B", "FUT")],
        "short_future": [("S", "FUT")]
    }

    # Reorder legs if needed
    if strategy_name == "iron_condor":
        ce_legs = sorted([leg for leg in data if leg["option_type"] == "CE"], key=lambda x: x["strike"])
        pe_legs = sorted([leg for leg in data if leg["option_type"] == "PE"], key=lambda x: x["strike"], reverse=True)
        legs_ordered = [
            ("S", "CE", ce_legs[0]),
            ("B", "CE", ce_legs[1]),
            ("S", "PE", pe_legs[0]),
            ("B", "PE", pe_legs[1])
        ]
    else:
        legs_ordered = [(action, opt_type, data[i]) for i, (action, opt_type) in enumerate(strategies[strategy_name])]

    # Counter per type to ensure CE_1, PE_1 are aligned to what backend expects
    ce_count = pe_count = 1
    for trade_type, option_type, leg in legs_ordered:
        strike = leg.get("strike")
        price = leg.get("price")
        qty = leg.get("qty")
        order_type = "buy" if trade_type == "B" else "sell"

        if option_type == "CE":
            payload.update({
                f"ce_strike_price_{ce_count}": strike,
                f"ce_entry_price_{ce_count}": price,
                f"ce_no_of_lots_{ce_count}": qty,
                f"is_ce_{ce_count}_long": order_type
            })
            ce_count += 1

        elif option_type == "PE":
            payload.update({
                f"pe_strike_price_{pe_count}": strike,
                f"pe_entry_price_{pe_count}": price,
                f"pe_no_of_lots_{pe_count}": qty,
                f"is_pe_{pe_count}_long": order_type
            })
            pe_count += 1

        elif option_type == "FUT":
            payload.update({
                "future_entry_price": price,
                "future_no_of_lots": qty,
                "is_future_long": order_type
            })
    # print (payload)
    # exit(0)
    return payload






def filter_instruments(name=None, expiry=None, instrument_type=None, exchange=None):
    mask = pd.Series(True, index=instrument_df.index)

    # mapping of parameter → how to apply
    for col, val in {
        'name': name,
        'expiry': expiry,
        'instrument_type': instrument_type,
        'exchange': exchange
    }.items():
        if val is None:
            continue

        if col == 'exchange':
            # allow a single value or list
            values = val if isinstance(val, (list, tuple, set)) else [val]
            mask &= instrument_df[col].isin(values)
        else:
            mask &= instrument_df[col] == val

    return instrument_df[mask]


def lots_size_find(symbol,instrument_type):
    df = filter_instruments(name=symbol, instrument_type=instrument_type)
    if df.empty:
        return None
    lot_size_np = df.iloc[0]['lot_size']
    lot_size = int(lot_size_np)
    return lot_size

def build_payload_from_db(alert_id,basket_id, user_id):
    print ("trade going to live screener ")
    db_path = r"C:\Users\Alkalyme\Downloads\ato_project\ato_project\instance\ato_system.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF;")

    cursor.execute("SELECT symbol FROM alerts WHERE id = ?", (alert_id,))
    alert_row = cursor.fetchone()
    if not alert_row:
        raise ValueError("Alert not found.")
    alert_symbol = alert_row[0]

    cursor.execute("SELECT id, strategy FROM baskets WHERE alert_id = ? LIMIT 1", (alert_id,))
    basket_row = cursor.fetchone()
    if not basket_row:
        raise ValueError("No basket found for this alert.")
    basket_id, strategy_name = basket_row

    cursor.execute("""
        SELECT action, instrument_type, symbol, strike, expiry, quantity, price, premium, margin
        FROM legs WHERE basket_id = ?
    """, (basket_id,))
    leg_rows = cursor.fetchall()
    if not leg_rows:
        raise ValueError("No legs found for this basket.")

    data = []
    for leg in leg_rows:
        action, option_type, symbol, strike, expiry, qty, price, premium, margin = leg
        # print (leg)
        data.append({
            "instrument": symbol,
            "strike": strike if option_type != "FUT" else 0,
            "price": price or premium,
            "qty": qty//lots_size_find(symbol,option_type),
            "option_type": option_type,
            "lots": lots_size_find(symbol,option_type),
            "action": action,
            "expiry": datetime.fromisoformat(expiry).strftime('%Y-%m-%d') if expiry else None,
            "margin": margin,
            "name": alert_symbol
        })
    # print (data)
    # exit(0)
    login()
    payload = generate_strategy_payload(alert_id, strategy_name, data, user_id)
    response = call_php_insert_db_api(alert_id, payload)
    return response

def insert_eq_scanner_entries(eq_orders_data,alert_id):
    db_path = r"C:\Users\Alkalyme\Downloads\ato_project\ato_project\instance\ato_system.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # 1) Prepare data
        currundate = datetime.now().date().isoformat()
        instrument  = eq_orders_data[0]
        qty         = int(eq_orders_data[1]) if eq_orders_data[1] else 0
        price       = float(eq_orders_data[2]) if eq_orders_data[2] else 0.0
        user_id     = eq_orders_data[3]
        entry       = "entry"
        target      = ''
        stop_loss   = ''

        # 2) Get latest Nifty price
        row = fetch_data(
            "SELECT price FROM live_tick_nifty ORDER BY time DESC LIMIT 1"
        )
        nifty_on_buy = row[0][0] if row else 0
        # print(nifty_on_buy)

        # 3) Insert into eq_scanner
        insert_sql = """
        INSERT INTO eq_scanner (
            `Symbol Name`,
            `Quantity`,
            `Price`,
            `Date`,
            `Buy Condition`,
            `nifty on buy`,
            `target`,
            `stop_loss`,
            `userid`
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        rowid = query_execute_method(insert_sql, (
            instrument,
            qty,
            price,
            currundate,
            entry,
            nifty_on_buy,
            target,
            stop_loss,
            user_id
        ))
        live_scanner_id = rowid
        print(f"✅ Inserted EQ entry (live_scanner_id={live_scanner_id}): "
              f"{instrument}, qty={qty}, price={price}")

        # 4) Update alerts and baskets tables
        cursor.execute(
            "UPDATE alerts SET live_scanner_id = ? WHERE id = ?",
            (live_scanner_id, alert_id)
        )
        cursor.execute(
            "UPDATE baskets SET live_scanner_id = ? WHERE alert_id = ?",
            (live_scanner_id, alert_id)
        )

        conn.commit()
        print(f"✅ Updated alerts.id={alert_id} and baskets.alert_id={alert_id} "
              f"with live_scanner_id={live_scanner_id}")

        return live_scanner_id

    except Exception as e:
        conn.rollback()
        print("⚠️ Error during insert or update:", e)
        raise
    finally:
        conn.close()


    


