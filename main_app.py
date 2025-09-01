import re
import threading
from flask import Flask, request, jsonify, render_template
from celery import Celery
import time
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta,time
import json
import os
import pytz
from constants import (
    ACCESS_TOKEN_PATH,
    INSTRUMENTS_CSV_PATH,
    SQLITE_DB_PATH,
    TEMPLATE_FOLDER_PATH)
from send_live_screener import build_payload_from_db,insert_eq_scanner_entries
from exit_live_screener import verify_trades_data,send_full_exit
# Initialize Flask app
__author__ = 'hitesh.divekar'
app = Flask(__name__, template_folder=TEMPLATE_FOLDER_PATH)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLITE_DB_PATH
CORS(app, origins="*")  # Allow all origins (dev only)


import random
import pandas as pd
from global_connection import fetch_data
import requests
file_path = INSTRUMENTS_CSV_PATH
instrument_df = pd.read_csv(file_path)
# access_token = open(ACCESS_TOKEN_PATH).read()
from kiteconnect import KiteConnect, KiteTicker
access_token = open(r'\\Velocity\c\Users\kunal\Downloads\LIVE_TICK_HIGH_LOW_FLASK\LIVE_TICK_HIGH_LOW_FLASK\zerodha_access_token.txt').read()
kite = KiteConnect(api_key='zuuxkho8imp70m8c', access_token=access_token)
from sqlalchemy import event
from send_email import generate_and_send_email,generate_and_send_execution_email,generate_and_send_exit_email, send_gtt_created_email,send_order_success_email

from websocket_server import track_alert_task



# ========================================
# ALERTS ENDPOINTS
# ========================================


# Indian timezone setup
IST = pytz.timezone('Asia/Kolkata')

from models_db import db , Alert, Basket, Leg, RiskSetting
# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = SQLITE_DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = False

db.init_app(app)

from functools import wraps


def add_cors_headers(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        if hasattr(response, 'headers'):
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    return decorated_function


def get_lot_size_fn(token):
    filtered_df = instrument_df[instrument_df['instrument_token'] == token]
    if not filtered_df.empty:
        return filtered_df.iloc[0]['lot_size']








# Mock DB / user dictionary
# users_db = {
#     "6107a84358676f862be226daae343418": {"username": "Hitesh"},
#     "102": {"username": "Rahul"},
#     "103": {"username": "Amit"}
# }

@app.route('/user_get', methods=['POST'])
def user_get():
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"status": "error", "message": "user_id missing"}), 400

        # Run query
        query = f"""SELECT username FROM user_details WHERE user_id = '{user_id}'"""
        result = fetch_data(query)

        if result and len(result) > 0:
            username = result[0]["username"] if isinstance(result[0], dict) else result[0][0]
            return jsonify({"status": "success", "user_key": username})
        else:
            return jsonify({"status": "error", "message": "User not found"}), 404

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



def get_instrument_token(symbol=None, expiry=None, strike=None, instrument_type=None):
    """
    Lookup instrument_token & tradingsymbol from instrument_df for
    CE/PE, FUT and EQ.  Will try both 'tradingsymbol' and a
    'symbol' or 'name' column for equities.
    """
    if not symbol or not instrument_type:
        print("[Token Lookup Error] Missing symbol or instrument_type.")
        return None

    # make sure our inputs are uppercase strings
    sym = str(symbol).upper().strip()
    itype = str(instrument_type).upper().strip()

    # Options
    if itype in ("CE", "PE"):
        if not expiry or strike is None:
            print("[Token Lookup Error] Expiry or strike missing for option.")
            return None
        try:
            strike_price = float(strike)
        except ValueError:
            print("[Token Lookup Error] Invalid strike format.")
            return None

        df = instrument_df[
            (instrument_df["instrument_type"] == itype)
            & (instrument_df["expiry"] == expiry)
            & (instrument_df["strike"] == strike_price)
            & (instrument_df["name"].str.upper() == sym)
        ]

    # Futures
    elif itype == "FUT":
        if not expiry:
            print("[Token Lookup Error] Expiry missing for future.")
            return None

        df = instrument_df[
            (instrument_df["instrument_type"] == itype)
            & (instrument_df["expiry"] == expiry)
            & (instrument_df["name"].str.upper() == sym)
        ]

    # Equity
    elif itype == "EQ":
        # try tradingsymbol match first
        mask = (
            (instrument_df["instrument_type"] == itype)
            & (instrument_df["tradingsymbol"].str.upper() == sym)
        )
        df = instrument_df[mask]

        # if not found, try a 'symbol' or 'name' column
        if df.empty and "symbol" in instrument_df.columns:
            df = instrument_df[
                (instrument_df["instrument_type"] == itype)
                & (instrument_df["symbol"].str.upper() == sym)
            ]
            # print (df)
        if df.empty and "name" in instrument_df.columns:
            df = instrument_df[
                (instrument_df["instrument_type"] == itype)
                & (instrument_df["name"].str.upper() == sym)
            ]

    else:
        print(f"[Token Lookup Error] Unknown type: {instrument_type}")
        return None

    if df.empty:
        print(f"[Token Lookup Error] No match for {sym}, type={itype}")
        return None

    token = df.iloc[0]["instrument_token"]
    ts    = df.iloc[0]["tradingsymbol"]
    return token, ts





from typing import Optional

def get_tradingsymbol_from_csv(
    symbol: str,
    expiry: Optional[str],
    strike: Optional[float],
    instrument_type: str
) -> str:
    """
    Lookup the Kite tradingsymbol from instrument_df based on:
      - EQ:   symbol only
      - FUT:  symbol + expiry
      - CE/PE: symbol + expiry + strike
    Raises ValueError if not found.
    """
    df = instrument_df.copy()

    # filter by instrument type
    mask = df["instrument_type"] == instrument_type

    if instrument_type == "EQ":
        if "name" in df.columns:
            mask &= df["name"] == symbol
        else:
            mask &= df["tradingsymbol"] == symbol

    else:
        # parse expiry into a date
        try:
            exp_date = pd.to_datetime(expiry).date()
        except Exception:
            raise ValueError(f"Invalid expiry format: {expiry}")

        mask &= pd.to_datetime(df["expiry"], errors="coerce").dt.date == exp_date

        if instrument_type in ("CE", "PE"):
            mask &= df["strike"] == float(strike)

        # finally, ensure the underlying matches
        if "name" in df.columns:
            mask &= df["name"] == symbol
        else:
            # fallback if you only have tradingsymbol
            mask &= df["tradingsymbol"].str.startswith(symbol)

    candidates = df[mask]
    if candidates.empty:
        raise ValueError(f"No instrument found for {symbol} {expiry} {strike} {instrument_type}")

    # return the first tradingsymbol
    return candidates.iloc[0]["tradingsymbol"]


def get_instrument_id(symbol):
    df = instrument_df[instrument_df['tradingsymbol'] == symbol]
    return df.iloc[0]['instrument_token']




@app.route('/')
def index():
    return jsonify({
        'message': 'Advanced ATO Basket Builder API',
        'version': '1.0.0',
        'endpoints': {
            'alerts': '/api/alerts',
            'baskets': '/api/baskets',
            'legs': '/api/legs',
            'risk_settings': '/api/risk_settings'
        },
        'status': 'active'
    })

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected'
    })

# ========================================
# ALERTS ENDPOINTS
# ========================================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    try:
        # Always fetch directly from the URL (?userKey=...)
        user_key = request.args.get('userKey')
        if not user_key:
            return jsonify({'error': 'userKey required in URL'}), 401

        status = request.args.get('status')
        symbol = request.args.get('symbol')
        limit  = request.args.get('limit', type=int)

        # Only alerts for this user
        query = Alert.query.filter(Alert.session_user == user_key)

        if status:
            query = query.filter(Alert.status == status)
        if symbol:
            query = query.filter(Alert.symbol == symbol)

        query = query.order_by(Alert.created_at.desc())
        if limit:
            query = query.limit(limit)

        alerts = query.all()
        return jsonify({
            'alerts': [a.to_dict() for a in alerts],
            'count': len(alerts),
            'status': 'success'
        })

    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch alerts',
            'message': str(e),
            'error_type': e.__class__.__name__
        }), 500



#############################################################################################################################################################


def calculating_per_leg(symbol, expiry, strike, instrument_type,action, quantity, price):
    trading_symbol = get_tradingsymbol_from_csv(symbol, expiry, strike, instrument_type)
    exchange = 'NFO' if instrument_type in ('CE','PE','FUT') else 'NSE'

    if instrument_type in ("EQ", "FUT"):
        return round(((price or 0) * quantity),2)


    payload=[{"exchange":exchange,"tradingsymbol":trading_symbol,"transaction_type":"BUY" if action.upper().startswith("B") else"SELL","variety":kite.VARIETY_REGULAR,
              "product":kite.PRODUCT_NRML,"order_type":kite.ORDER_TYPE_MARKET,"quantity":quantity,"price":price or 0,"trigger_price":0}]
    margins = kite.order_margins(payload)
    return margins[0].get("total", 0.0)



@app.route('/api/alerts', methods=['POST'])
def create_alert():
    """Create a new alert with baskets and legs – updated with proper margin & risk settings"""
    try:
        data = request.get_json()
        required_fields = ['symbol', 'operator', 'threshold', 'valid_till', 'baskets']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': 'Missing required field', 'field': field}), 400

        try:
            valid_till = datetime.fromisoformat(data['valid_till'].replace('Z', '+00:00'))
        except:
            return jsonify({ 'error': 'Invalid datetime format for valid_till', 'message': 'Use ISO format: YYYY-MM-DDTHH:MM:SS' }), 400

        
        user_key = data.get('session_user') or request.args.get('userKey')
        alert = Alert( symbol=data['symbol'], operator=data['operator'], threshold=float(data['threshold']), valid_till=valid_till,
            status=data.get('status', 'waiting'), session_user=user_key, total_margin_required=data.get('total_margin_required', 0) )
        
        db.session.add(alert)
        db.session.flush()  
        
        
        for basket_data in data['baskets']:
            
            basket = Basket( alert_id=alert.id, label=basket_data['label'], strategy=basket_data.get('strategy', 'custom'), 
                            risk_mode=basket_data.get('risk_mode', 'individual'), margin_required=data.get('total_margin_required', 0) )
            db.session.add(basket)
            db.session.flush() 
            

            for leg_data in basket_data['legs']:
                expiry = None
                if leg_data.get('expiry'):
                    try:
                        expiry = datetime.fromisoformat(leg_data['expiry'])
                    except:
                        expiry = datetime.strptime(leg_data['expiry'], '%Y-%m-%d')
                
                itype = leg_data['instrument_type'].upper()
                qty   = int(leg_data['quantity'])
                px    = leg_data.get('price') or leg_data.get('premium') or 0

                if itype == 'EQ':
                
                    leg_margin = px * qty
                else:
                    leg_margin = calculating_per_leg( symbol=leg_data['symbol'], expiry=leg_data['expiry'], strike=leg_data.get('strike'), 
                                                     instrument_type=itype, action=leg_data['action'], quantity=qty, price=px )

                leg = Leg( basket_id=basket.id, action=leg_data['action'], instrument_type=itype, symbol=leg_data['symbol'], strike=leg_data.get('strike'),
                          expiry=expiry, quantity=qty, price=leg_data.get('price'), premium=leg_data.get('premium'), premium_type=leg_data.get('premium_type'), 
                          margin=leg_margin, sl=leg_data.get('sl'), tp=leg_data.get('tp') )

                db.session.add(leg)
            
            rm = basket_data.get('risk_management', {})
            settings = rm.get('settings', {}) 

            for risk_type, cfg in settings.items():
                if risk_type == "individual":
                    sl_type = cfg.get("defaultSlType")
                    if sl_type:
                        rs_sl = RiskSetting( basket_id=basket.id, risk_type="individual", option_type=sl_type )
                        rs_sl.set_settings({"slValue": cfg.get("slValue")})
                        db.session.add(rs_sl)
                        
                    tp_type = cfg.get("defaultTpType")
                    if tp_type:
                        rs_tp = RiskSetting( basket_id=basket.id, risk_type="individual", option_type=tp_type )
                        rs_tp.set_settings({"tpValue": cfg.get("tpValue")})
                        db.session.add(rs_tp)
                else:
                    sel = cfg.get("selectedOption")
                    if sel:
                        rs = RiskSetting( basket_id=basket.id, risk_type=risk_type, option_type=sel )
                        rs.set_settings(cfg.get("settings", {}))
                        db.session.add(rs)

        db.session.commit()
        # print (alert.id)
        track_alert_task.delay(alert.id)
        generate_and_send_email(alert, data['baskets'])
        print(f"✅ ATO Created Successfully: ID={alert.id}, Total Margin=₹{alert.total_margin_required:,}")
        return jsonify({ 'alert': alert.to_dict(), 'message': 'Alert created successfully with margin & risk settings', 'status': 'success' }), 201

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating alert: {e}")
        return jsonify({'error': 'Failed to create alert', 'message': str(e)}), 500


#############################################################################################################################################################

@app.route('/api/alerts/<alert_id>', methods=['GET'])
def get_alert(alert_id):
    """Get a specific alert by ID"""
    try:
        alert = db.session.get(Alert, alert_id)
        
        if not alert:
            return jsonify({
                'error': 'Alert not found',
                'alert_id': alert_id
            }), 404
        
        return jsonify({
            'alert': alert.to_dict(),
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch alert',
            'message': str(e)
        }), 500



@app.route('/api/alerts/<alert_id>', methods=['PUT'])
def update_alert(alert_id):
    """Update an existing alert"""
    try:
        alert = db.session.get(Alert, alert_id)
        
        if not alert:
            return jsonify({
                'error': 'Alert not found',
                'alert_id': alert_id
            }), 404
        
        data = request.get_json()
        
        # Update alert fields
        if 'symbol' in data:
            alert.symbol = data['symbol']
        if 'operator' in data:
            alert.operator = data['operator']
        if 'threshold' in data:
            alert.threshold = float(data['threshold'])
        if 'valid_till' in data:
            alert.valid_till = datetime.fromisoformat(data['valid_till'].replace('Z', '+00:00'))
        if 'status' in data:
            alert.status = data['status']
            
            # Set timestamps based on status
            if data['status'] == 'triggered' and not alert.triggered_at:
                alert.triggered_at = datetime.now()
            elif data['status'] == 'completed' and not alert.completed_at:
                alert.completed_at = datetime.now()
            elif data['status'] == 'cancelled' and not alert.cancelled_at:
                alert.cancelled_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'alert': alert.to_dict(),
            'message': 'Alert updated successfully',
            'status': 'success'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to update alert',
            'message': str(e)
        }), 500
        
        
        


@app.route('/api/alerts/<alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    """Delete an alert and all related data"""
    try:
        alert = db.session.get(Alert, alert_id)
        
        if not alert:
            return jsonify({
                'error': 'Alert not found',
                'alert_id': alert_id
            }), 404
        
        # Check if alert can be deleted (only waiting alerts)
        if alert.status not in ['waiting', 'cancelled']:
            return jsonify({
                'error': 'Cannot delete alert',
                'message': 'Only waiting or cancelled alerts can be deleted',
                'current_status': alert.status
            }), 400
        
        db.session.delete(alert)
        db.session.commit()
        
        return jsonify({
            'message': 'Alert deleted successfully',
            'alert_id': alert_id,
            'status': 'success'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to delete alert',
            'message': str(e)
        }), 500




def has_hedge_leg(basket):
    for leg in basket.legs:
        if leg.action == 'B' and ('CE' in leg.symbol or 'PE' in leg.symbol):
            return True
    return False

IST = pytz.timezone("Asia/Kolkata")

PREOPEN_BLOCK_START = time(9, 8, 0)
PREOPEN_BLOCK_END   = time(9, 15, 0)
AMO_EQUITY_START    = time(15, 45, 0)
AMO_EQUITY_END      = time(8, 59, 59)

def now_ist(): return datetime.now(IST)
def in_time_range(t, start, end): return start <= t <= end

def is_preopen_block():
    d = now_ist()
    if d.weekday() >= 5:  # Sat/Sun
        return False
    return in_time_range(d.time(), PREOPEN_BLOCK_START, PREOPEN_BLOCK_END)

def is_amo_window_equity():
    t = now_ist().time()
    return (t >= AMO_EQUITY_START) or (t <= AMO_EQUITY_END)

def is_fo_symbol(tradingsymbol: str) -> bool:
    ts = tradingsymbol.upper()
    return ('FUT' in ts) or ts.endswith('CE') or ts.endswith('PE')

def detect_segment_and_product(tradingsymbol):
    ts = tradingsymbol.upper()
    if 'FUT' in ts or ts[-2:] in ['CE', 'PE']:
        return 'NFO', 'NRML'
    return 'NSE', 'CNC'

def detect_segment_and_product(tradingsymbol):

    tradingsymbol = tradingsymbol.upper()
    
    # Basic F&O pattern detection
    if 'FUT' in tradingsymbol or tradingsymbol[-2:] in ['CE', 'PE']:
        return 'NFO', 'NRML'  # F&O trades go to NFO and use NRML for swing
    else:
        return 'NSE', 'CNC'   # Equity delivery trade


def place_order_safe(tradingsymbol, qty, price, action, order_type,
                     enable_gtt_fallback=True, wait_for_open=True):
    ts = tradingsymbol.upper()
    segment, product_type = detect_segment_and_product(ts)

    # Choose variety
    order_variety = KiteConnect.VARIETY_REGULAR
    if not is_fo_symbol(ts) and is_amo_window_equity() and order_type.upper() in ("LIMIT", "MARKET"):
        order_variety = KiteConnect.VARIETY_AMO

    # Handle pre-open block
    if is_preopen_block():
        if enable_gtt_fallback:
            g = place_gtt_equivalent(ts, segment, qty, price, action, order_type)
            if g:
                send_gtt_created_email(ts, qty, price, action, order_type, g["gtt_id"])
                return ("GTT", g["gtt_id"], None)
            return None
        elif wait_for_open:
            target = now_ist().replace(hour=9, minute=15, second=5, microsecond=0)
            if target < now_ist():
                target += timedelta(days=1)
            sleep_seconds = (target - now_ist()).total_seconds()
            print(f"[ORDER] Pre-open block. Waiting {int(sleep_seconds)}s to place at open...")
            import time; time.sleep(max(0, sleep_seconds))
        else:
            print("[ORDER] Pre-open blocked and no fallback chosen.")
            return None

    transaction_type = (KiteConnect.TRANSACTION_TYPE_BUY
                        if action.upper() in ('B','BUY') else KiteConnect.TRANSACTION_TYPE_SELL)
    kite_order_type  = (KiteConnect.ORDER_TYPE_LIMIT
                        if order_type.upper() == 'LIMIT' else KiteConnect.ORDER_TYPE_MARKET)

    order_args = {
        'variety': order_variety,
        'exchange': segment,
        'tradingsymbol': ts,
        'transaction_type': transaction_type,
        'quantity': int(qty),
        'product': product_type,
        'order_type': kite_order_type,
        'validity': KiteConnect.VALIDITY_DAY
    }
    if kite_order_type == KiteConnect.ORDER_TYPE_LIMIT:
        order_args['price'] = float(price)

    try:
        order_id = kite.place_order(**order_args)
        filled_qty = int(qty)  # adjust if you fetch actual fills later
        executed_price = float(price) if kite_order_type == KiteConnect.ORDER_TYPE_LIMIT else None

        print(f"[ORDER] Placed {action} {ts} qty={qty} price={price} | Variety={order_variety} | Segment={segment} | Product={product_type} | ID={order_id}")

        # ✅ Your email helper
        send_order_success_email(
            tradingsymbol=ts, qty=qty, price=price, action=action, order_type=order_type,
            order_id=order_id, filled_qty=filled_qty, executed_price=executed_price
        )
        return order_id, filled_qty, executed_price

    except Exception as e:
        msg = str(e) or ""
        print(f"[ORDER ERROR] {msg}")

        # If rejected due to pre-open, try GTT fallback on the spot
        if enable_gtt_fallback and ("pre-open" in msg.lower() or re.search(r"order collection .* over", msg, re.I)):
            g = place_gtt_equivalent(ts, segment, qty, price, action, order_type)
            if g:
                send_gtt_created_email(ts, qty, price, action, order_type, g["gtt_id"])
                return ("GTT", g["gtt_id"], None)

        # If we still are in the window & allowed to wait, retry just after 09:15
        if wait_for_open and is_preopen_block():
            target = now_ist().replace(hour=9, minute=15, second=5, microsecond=0)
            if target < now_ist():
                target += timedelta(days=1)
            sleep_seconds = (target - now_ist()).total_seconds()
            print(f"[ORDER] Retrying at market open in {int(sleep_seconds)}s...")
            import time; time.sleep(max(0, sleep_seconds))
            try:
                order_id = kite.place_order(**order_args)
                filled_qty = int(qty)
                executed_price = float(price) if kite_order_type == KiteConnect.ORDER_TYPE_LIMIT else None
                print(f"[ORDER] Placed on retry {action} {ts} qty={qty} | ID={order_id}")
                send_order_success_email(
                    tradingsymbol=ts, qty=qty, price=price, action=action, order_type=order_type,
                    order_id=order_id, filled_qty=filled_qty, executed_price=executed_price
                )
                return order_id, filled_qty, executed_price
            except Exception as e2:
                print(f"[ORDER ERROR RETRY] {e2}")

        return None

def place_gtt_equivalent(tradingsymbol, exchange, qty, limit_price, action, order_type):
    """
    Create a SINGLE GTT trigger @ limit_price. When it fires, it places the same LIMIT/MARKET.
    """
    try:
        last_price = 0.0
        try:
            ltp_map = kite.ltp([f"{exchange}:{tradingsymbol}"])
            last_price = float(ltp_map[f"{exchange}:{tradingsymbol}"]["last_price"])
        except Exception:
            pass

        trigger_type   = KiteConnect.GTT_TYPE_SINGLE
        trigger_values = [float(limit_price)]

        orders = [{
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "transaction_type": KiteConnect.TRANSACTION_TYPE_BUY if action.upper() in ('B','BUY') else KiteConnect.TRANSACTION_TYPE_SELL,
            "quantity": int(qty),
            "order_type": KiteConnect.ORDER_TYPE_LIMIT if order_type.upper()=="LIMIT" else KiteConnect.ORDER_TYPE_MARKET,
            "product": detect_segment_and_product(tradingsymbol)[1],
            "price": float(limit_price) if order_type.upper()=="LIMIT" else 0.0
        }]

        gtt_id = kite.place_gtt(
            trigger_type=trigger_type,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            trigger_values=trigger_values,
            last_price=last_price,
            orders=orders
        )
        print(f"[GTT] Created SINGLE trigger for {tradingsymbol} @ {limit_price} (id={gtt_id})")
        return {"gtt_id": gtt_id}
    except Exception as e:
        print(f"[GTT ERROR] {e}")
        return None






# def place_order(tradingsymbol,qty,price,action,order_type):
#     try:
#         segment, product_type = detect_segment_and_product(tradingsymbol)
#         transaction_type = KiteConnect.TRANSACTION_TYPE_BUY if action.upper() == 'B' else KiteConnect.TRANSACTION_TYPE_SELL
#         kite_order_type = KiteConnect.ORDER_TYPE_LIMIT if order_type.upper() == 'LIMIT' else KiteConnect.ORDER_TYPE_MARKET
#         order_args = {
#             'variety': KiteConnect.VARIETY_REGULAR,
#             'exchange': segment,
#             'tradingsymbol': tradingsymbol,
#             'transaction_type': transaction_type,
#             'quantity': qty,
#             'product': product_type,
#             'order_type': kite_order_type,
#             'validity': KiteConnect.VALIDITY_DAY
#         }

#         if kite_order_type == KiteConnect.ORDER_TYPE_LIMIT:
#             order_args['price'] = price

#         order_id = kite.place_order(**order_args)
#         filled_qty = qty
#         executed_price = price
#         print(f"[ORDER] Placed {action} {tradingsymbol} qty={qty} price={price} | Segment={segment} | Product={product_type} | ID={order_id}")
#         print(f"[ORDER] Placed {action} {tradingsymbol} qty={qty} price={price} | ID={order_id}")
#         send_order_success_email(tradingsymbol=tradingsymbol,qty=qty,price=price,action=action,order_type=order_type,
#                                  order_id=order_id,filled_qty=filled_qty,executed_price=executed_price)
#         return order_id, filled_qty, executed_price
#     except Exception as e:
#         print(f"[ORDER ERROR] {e}")
#         return None






@app.route('/api/alerts/<string:alert_id>/trigger', methods=['POST'])
def trigger_alert_enhanced(alert_id):
    """Enhanced trigger with comprehensive error tracking and robust threading for scanner integration"""


    execution_log = {
        'alert_id': alert_id,
        'timestamp': datetime.now().isoformat(),
        'steps': [],
        'errors': [],
        'warnings': [],
        'success': False
    }

    def run_in_thread(target, *args, **kwargs):
        try:
            t = threading.Thread(target=target, args=args, kwargs=kwargs)
            t.daemon = True
            t.start()
        except Exception as e:
            execution_log['warnings'].append({
                'step': 'ThreadStart',
                'error': str(e),
                'message': f'Failed to start thread for {target.__name__}'
            })

    try:
        # STEP 1: Alert Lookup & Validation
        alert = Alert.query.filter_by(id=alert_id).first()
        if not alert:
            return jsonify({
                'success': False, 
                'error': 'Alert not found', 
                'alert_id': alert_id,
                'execution_log': execution_log
            }), 404

        # STEP 2: Status Validation
        print(alert.status)
        if alert.status != 'waiting':
            return jsonify({
                'success': False,
                'error': 'Cannot trigger alert',
                'message': 'Only waiting alerts can be triggered',
                'current_status': alert.status,
                'execution_log': execution_log
            }), 400

        # STEP 3: Update Alert Status
        alert.status = 'triggered'
        alert.triggered_at = datetime.now()

        # STEP 4: Process Each Basket
        basket_results = []
        for basket_idx, basket in enumerate(alert.baskets):
            basket_log = {'basket_id': basket.id, 'legs': []}
            try:
                basket.status = 'active'
                legs = basket.legs
                if has_hedge_leg(basket):
                    sort_order = sorted(legs, key=lambda l: 0 if l.action.upper().startswith('B') else 1)
                else:
                    sort_order = legs
                for leg_idx, leg in enumerate(sort_order):
                    leg_id = leg.id
                    leg_log = {'leg_id': leg_id, 'status': 'started'}
                    try:
                        print(f"{leg.action} {leg.quantity} {leg.symbol}")
                        ptype = (leg.premium_type or '').lower()
                        if ptype == 'limit':
                            leg.status = 'executed'
                            leg.executed_at = datetime.now()
                            leg_log['status'] = 'executed_limit'
                            continue
                        try:
                            instr = leg.instrument_type
                            exp = leg.expiry
                            expiry_str = exp.strftime('%Y-%m-%d') if isinstance(exp, datetime) else (exp or '')
                            strike = leg.strike or 0
                            if instr in {'CE', 'PE'}:
                                token, trading_symbol = get_instrument_token(leg.symbol, expiry_str, strike, instr)
                            elif instr == 'FUT':
                                token, trading_symbol = get_instrument_token(leg.symbol, expiry_str, 0, instr)
                            else:
                                token, trading_symbol = get_instrument_token(leg.symbol, '', 0, 'EQ')
                            if not token:
                                raise ValueError(f"No token found for {leg.symbol}")
                        except Exception as e:
                            leg_log['status'] = 'token_failed'
                            leg_log['error'] = str(e)
                            continue
                        try:
                            mdata = kite.quote([token]).get(str(token), {})
                            ltp = mdata.get('last_price', 0)
                            depth = mdata.get('depth', {})
                            buys = depth.get('buy', [])
                            sells = depth.get('sell', [])
                            best_bid = buys[0].get('price', 0) if buys else 0
                            best_ask = sells[0].get('price', 0) if sells else 0
                            mid_price = round((best_bid + best_ask) / 2, 2) if (best_bid and best_ask) else ltp
                            
                        except Exception as e:
                            ltp = best_bid = best_ask = mid_price = 0
                        if ptype == 'best_bid':
                            chosen_price = best_bid if best_bid else ltp
                        elif ptype == 'best_ask':
                            chosen_price = best_ask if best_ask else ltp
                        elif ptype == 'mid':
                            chosen_price = mid_price if mid_price else ltp
                        else:
                            chosen_price = ltp
                        try:
                            order_id, filled_qty, executed_price = place_order_safe(
                            tradingsymbol=trading_symbol,
                            qty=leg.quantity,
                            price=chosen_price,
                            action=leg.action,
                            order_type=ptype or 'market',
                            enable_gtt_fallback=True,   # auto-GTT in pre-open
                            wait_for_open=True          # or wait until 09:15 if GTT not possible
                        )

                            if order_id is None:
                                raise RuntimeError(f"Order placement returned None for {trading_symbol}")
                        except Exception as e:
                            leg_log['status'] = 'order_failed'
                            leg_log['error'] = str(e)
                            continue
                        try:
                            if instr in {'CE', 'PE'}:
                                leg.premium = executed_price
                            else:
                                leg.price = executed_price
                            leg.quantity = filled_qty
                            leg.trade_instrument_token = order_id
                            leg.status = 'executed'
                            leg.executed_at = datetime.now()
                            leg_log['status'] = 'executed'
                            leg_log['executed_price'] = executed_price
                            leg_log['filled_qty'] = filled_qty
                        except Exception as e:
                            leg_log['status'] = 'update_failed'
                            leg_log['error'] = str(e)
                    except Exception as e:
                        leg_log['status'] = 'failed'
                        leg_log['error'] = str(e)
                    basket_log['legs'].append(leg_log)
                basket_results.append(basket_log)
            except Exception as e:
                basket_results.append({
                    'basket_id': basket.id, 
                    'status': 'failed', 
                    'error': str(e)
                })

        # STEP 7: Database Commit
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise

        # STEP 8: Live Scanner Integration (threaded, errors only logged)
        user_key = alert.session_user
        for basket in alert.baskets:
            try:
                if basket.strategy == 'custom':
                    for leg in basket.legs:
                        if leg.instrument_type == 'EQ':
                            try:
                                instrument = leg.symbol
                                qty = leg.quantity or 0
                                price = leg.price or 0.0
                                eq_data = [instrument, qty, price, user_key]
                                run_in_thread(insert_eq_scanner_entries, eq_data, alert_id)
                            except Exception as e:
                                execution_log['warnings'].append({
                                    'step': 'EQScannerThread',
                                    'error': str(e),
                                    'message': f'Error starting EQ scanner thread for leg {leg.id}'
                                })
                else:
                    try:
                        run_in_thread(build_payload_from_db,alert_id, basket.id,user_key)
                    except Exception as e:
                        execution_log['warnings'].append({
                            'step': 'BasketScannerThread',
                            'error': str(e),
                            'message': f'Error starting basket scanner thread for basket {basket.id}'
                        })
            except Exception as e:
                execution_log['warnings'].append({
                    'step': 'ScannerThread',
                    'error': str(e),
                    'message': f'Error in scanner thread for basket {basket.id}'
                })

        # STEP 9: Email Generation
        try:
            generate_and_send_execution_email(alert)
        except Exception as e:
            execution_log['warnings'].append({
                'step': 'Email',
                'error': str(e),
                'message': 'Email failed but trade execution succeeded'
            })

        # STEP 10: Final Success
        execution_log['success'] = True

        return jsonify({
            'success': True,
            'alert': alert.to_dict(),
            'message': 'Alert triggered and all legs executed successfully',
            'status': 'success',
            'execution_log': execution_log,
            'basket_results': basket_results,
            'warnings': execution_log['warnings']
        }), 200

    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        execution_log['success'] = False
        return jsonify({
            'success': False,
            'error': 'Failed to trigger alert',
            'message': str(e),
            'execution_log': execution_log
        }), 500








@app.route('/api/alerts/<alert_id>/complete', methods=['POST']) 
def complete_alert(alert_id):
    """Mark an alert as completed"""
    try:
        alert = db.session.get(Alert, alert_id)
        
        if not alert:
            return jsonify({
                'error': 'Alert not found',
                'alert_id': alert_id
            }), 404
        
        data = request.get_json() or {}
        
        # Update alert status
        alert.status = 'completed'
        alert.completed_at = datetime.now()
        
        # Mark all baskets as exited
        for basket in alert.baskets:
            if basket.status != 'exited':
                basket.status = 'exited'
                basket.exited_at = datetime.now()
                basket.exit_reason = data.get('exit_reason', 'Manual completion')
                
                for leg in basket.legs:
                    if leg.status != 'exited':
                        leg.status = 'exited'
                        leg.exited_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'alert': alert.to_dict(),
            'message': 'Alert completed successfully',
            'status': 'success'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to complete alert',
            'message': str(e)
        }), 500

# ========================================
# BASKETS ENDPOINTS
# ========================================

@app.route('/api/baskets', methods=['GET'])
def get_baskets():
    """Get all baskets with optional filtering"""
    try:
        # Query parameters
        alert_id = request.args.get('alert_id')
        status = request.args.get('status')
        strategy = request.args.get('strategy')
        limit = request.args.get('limit', type=int)
        
        query = Basket.query
        
        # Apply filters
        if alert_id:
            query = query.filter(Basket.alert_id == alert_id)
        if status:
            query = query.filter(Basket.status == status)
        if strategy:
            query = query.filter(Basket.strategy == strategy)
        
        # Order by creation date (newest first)
        query = query.order_by(Basket.created_at.desc())
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        baskets = query.all()
        
        return jsonify({
            'baskets': [basket.to_dict() for basket in baskets],
            'count': len(baskets),
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': 'Failed to fetch baskets',
            'message': str(e)
        }), 500




def check_and_update_basket_alert_exit(basket, alert, exit_reason):
    """Mark basket and alert as completed if all legs are exited."""
    try:
        leg_statuses = [l.status for l in basket.legs] if basket and basket.legs else []
        all_exited = all(l.status == 'exited' for l in basket.legs)
        if all_exited:
            basket.status      = 'exited'
            basket.exited_at   = datetime.now()
            basket.exit_reason = exit_reason
            siblings = Basket.query.filter_by(alert_id=alert.id).all()
            all_siblings_exited = all(b.status == 'exited' for b in siblings)
            if all_siblings_exited:
                alert.status       = 'completed'
                alert.completed_at = datetime.now()
    except Exception as e:
        import traceback
        print("❌ ERROR in check_and_update_basket_alert_exit:", traceback.format_exc())
        raise



def has_main_leg_for_exit(basket):
    """Return True if basket has any SELL CE/PE legs."""
    try:
        if not basket or not basket.legs:
            return False
        for leg in basket.legs:
            if leg.action == 'S' and ('CE' in leg.symbol or 'PE' in leg.symbol):
                return True
        return False
    except Exception as e:
        import traceback
        print("❌ ERROR in has_main_leg_for_exit:", traceback.format_exc())
        raise

@event.listens_for(db.session, "after_rollback")
def after_rollback(session):
    print("Session rolled back!")

def _compute_and_assign(leg, exit_qty, ptype, exit_reason):
    """
    Safe exit executor for a single leg (EQ / CE-PE / FUT) using place_order_safe.
    - Respects exit_qty passed by caller.
    - Uses bid/ask/mid/ltp based on exit_price_type (ptype).
    - Handles GTT fallback without computing PnL until it actually fills.
    - Never reads filled_qty unless order succeeded.
    """
    from datetime import datetime
    try:
        leg.partial_exits = leg.partial_exits or []

        # ── Resolve instrument → token & tradingsymbol ──────────────────────
        instr = getattr(leg, 'instrument_type', '')  # 'EQ' | 'CE' | 'PE' | 'FUT'
        exp   = getattr(leg, 'expiry', '') or ''
        expiry_str = exp.strftime('%Y-%m-%d') if hasattr(exp, 'strftime') else str(exp or '')
        strike = int(getattr(leg, 'strike', 0) or 0)

        if instr in {'CE', 'PE'}:
            token, symbol = get_instrument_token(leg.symbol, expiry_str, strike, instr)
        elif instr == 'FUT':
            token, symbol = get_instrument_token(leg.symbol, expiry_str, 0, 'FUT')
        else:
            token, symbol = get_instrument_token(leg.symbol, '', 0, 'EQ')

        # ── Live quotes (ltp / depth) ───────────────────────────────────────
        q = kite.quote([token]).get(str(token), {}) if token else {}
        ltp   = q.get('last_price', 0) or 0
        depth = q.get('depth', {}) or {}
        buys  = depth.get('buy', []) or []
        sells = depth.get('sell', []) or []
        best_bid = (buys[0]['price'] if buys else 0) or 0
        best_ask = (sells[0]['price'] if sells else 0) or 0
        mid      = round((best_bid + best_ask) / 2, 2) if (best_bid and best_ask) else ltp

        ptype = (ptype or 'market').lower()
        if   ptype == 'best_bid': chosen = best_bid or ltp
        elif ptype == 'best_ask': chosen = best_ask or ltp
        elif ptype == 'mid':      chosen = mid or ltp
        else:                     chosen = ltp  # 'market' or anything else

        # ── Place the exit using your SAFE helper ───────────────────────────
        exit_action = 'S' if getattr(leg, 'action', 'S') == 'B' else 'B'

        res = place_order_safe(
            tradingsymbol=symbol,
            qty=int(exit_qty),
            price=chosen,
            action=exit_action,
            order_type=ptype or 'market',
            enable_gtt_fallback=True,
            wait_for_open=True
            # add product_override=leg.product if your helper supports it
        )

        # Hard failure → raise; do NOT touch filled_qty
        if not res:
            raise RuntimeError(
                f"Exit order failed | leg_id={getattr(leg, 'id', 'N/A')} "
                f"symbol={symbol} tried_qty={exit_qty}"
            )

        order_id, filled_qty, exec_price = res
        # NEW: if not filled yet, record a pending partial and return safely
        # PENDING FILL? -> mark & bail out safely
        if exec_price is None or not filled_qty:
            leg.partial_exits.append({
                'exit_price': None,
                'exit_quantity': int(exit_qty),
                'exit_timestamp': datetime.now().isoformat(),
                'exit_price_type': ptype,
                'pnl': None,
                'exit_reason': f"{exit_reason} (pending fill, order_id={order_id})"
            })
            leg.exit_price_type = ptype
            leg.exit_timestamp  = datetime.now()
            leg.exit_reason     = exit_reason
            # >>> Return 0.0 as a sentinel to callers: “placed but pending fill”
            return 0.0
        
        
        # Pre‑open / fallback path: ("GTT", gtt_id, None)
        if order_id == "GTT":
            leg.partial_exits.append({
                'exit_price': None,
                'exit_quantity': int(exit_qty),
                'exit_timestamp': datetime.now().isoformat(),
                'exit_price_type': ptype,
                'pnl': None,
                'exit_reason': f"{exit_reason} (GTT id={filled_qty})"
            })
            leg.exit_price_type = ptype
            leg.exit_timestamp  = datetime.now()
            leg.exit_reason     = exit_reason
            # No PnL yet; will be realized on actual fill
            return 0.0

        # ── Success path: compute PnL for actually filled qty only ──────────
        # Use exchange lot size for F&O; default 1 for EQ
        if instr in {'CE', 'PE', 'FUT'}:
            try:
                lot_size = int(get_lot_size_fn(token))
            except Exception:
                lot_size = int(getattr(leg, 'lot_size', 1) or 1)
        else:
            lot_size = int(getattr(leg, 'lot_size', 1) or 1)

        actual_qty = int(filled_qty) * lot_size

        entry_price = (
            getattr(leg, 'premium', None)
            or getattr(leg, 'price', None)
            or 0
        )

        if getattr(leg, 'action', 'S') == 'B':
            pnl = (exec_price - entry_price) * actual_qty
        else:
            pnl = (entry_price - exec_price) * actual_qty

        leg.pnl = (leg.pnl or 0) + pnl

        # Append partial record
        leg.partial_exits.append({
            'exit_price': exec_price,
            'exit_quantity': int(filled_qty),
            'exit_timestamp': datetime.now().isoformat(),
            'exit_price_type': ptype,
            'pnl': pnl,
            'exit_reason': exit_reason
        })

        # Weighted‑avg exit price across partials
        total_qty  = sum(r.get('exit_quantity', 0) for r in leg.partial_exits if r.get('exit_quantity') is not None)
        total_cost = sum((r.get('exit_price') or 0) * r.get('exit_quantity', 0) for r in leg.partial_exits)
        wap = (total_cost / total_qty) if total_qty else exec_price

        leg.exit_price      = wap
        leg.exit_quantity   = total_qty
        leg.exit_price_type = ptype
        leg.exit_timestamp  = datetime.now()
        leg.exit_reason     = exit_reason

        return pnl

    except Exception as e:
        import traceback
        print(
            f"❌ ERROR IN _compute_and_assign | leg_id={getattr(leg, 'id', 'N/A')} "
            f"symbol={getattr(leg, 'symbol', 'N/A')} tried_qty={exit_qty} ptype={ptype} -> {e}"
        )
        print(traceback.format_exc())
        raise


@app.route('/api/baskets/<int:basket_id>/exit-legs_all', methods=['POST'])
def exit_basket_legs(basket_id):
    """Partial, single, or full exit of all legs in a basket (idempotent & resilient)."""
    import threading
    from datetime import datetime

    def run_in_thread(target, *args, **kwargs):
        try:
            t = threading.Thread(target=target, args=args, kwargs=kwargs)
            t.daemon = True
            t.start()
        except Exception as e:
            print(f"❌ Failed to start thread for {target.__name__}: {e}")

    try:
        basket = db.session.get(Basket, basket_id)
        if not basket:
            return jsonify({'success': False, 'message': 'Basket not found'}), 404

        alert = db.session.get(Alert, basket.alert_id)
        user_key = alert.session_user if alert else None

        # Only triggered alerts can be exited (unchanged)
        if not alert or alert.status != 'triggered':
            return jsonify({
                'success': False,
                'message': 'Alert must be triggered to exit legs',
                'current_status': alert.status if alert else None
            }), 400

        data = request.get_json() or {}
        is_partial     = bool(data.get('is_partial_exit', False))
        exit_all       = bool(data.get('exit_all_legs', False))
        leg_index      = data.get('leg_index')
        exit_qty       = data.get('exit_quantity')
        exit_reason    = data.get('exit_reason', 'Manual exit')
        ptype_override = (data.get('exit_price_type') or '').lower()

        # Helper: safe compute wrapper — never lets None math throw
        def safe_compute_and_assign(leg, qty, ptype, reason):
            # No-op if already exited / nothing to do
            if (leg.status == 'exited') or (not leg.quantity) or qty <= 0:
                return 0.0
            try:
                return _compute_and_assign(leg, qty, ptype, reason)
            except Exception as e:
                # Log only; do not raise → keep endpoint 200 and idempotent
                import traceback
                print(f"❌ ERROR IN _compute_and_assign (guarded) | leg_id={getattr(leg,'id','N/A')} "
                      f"symbol={getattr(leg,'symbol','N/A')} qty={qty} type={ptype}: {e}")
                print(traceback.format_exc())
                # mark an attempted exit record so we don’t retry infinitely
                leg.exit_price_type = ptype
                leg.exit_reason = f"{reason} (compute error)"
                return 0.0

        # PARTIAL EXIT
        if is_partial:
            if leg_index is None or exit_qty is None:
                return jsonify({'success': False, 'message': 'leg_index and exit_quantity required'}), 400

            if leg_index < 0 or leg_index >= len(basket.legs):
                return jsonify({'success': False, 'message': 'Invalid leg_index'}), 400

            leg = basket.legs[leg_index]

            if leg.status == 'exited' or leg.quantity <= 0:
                return jsonify({'success': True, 'message': 'Leg already exited; nothing to do'}), 200

            if exit_qty > leg.quantity:
                return jsonify({'success': False, 'message': 'Invalid exit_quantity'}), 400

            ptype = ptype_override or (leg.premium_type or 'market')
            safe_compute_and_assign(leg, exit_qty, ptype, exit_reason)

            # Reduce qty and flip status if fully exited
            leg.quantity = max(0, (leg.quantity or 0) - int(exit_qty))
            if leg.quantity == 0:
                leg.status = 'exited'
                leg.exited_at = datetime.now()

            check_and_update_basket_alert_exit(basket, alert, exit_reason)
            message = 'Partial exit executed successfully'

        # EXIT ALL LEGS
        elif exit_all:
            legs = list(basket.legs or [])
            if not legs:
                return jsonify({'success': True, 'message': 'No legs in basket; nothing to exit'}), 200

            # keep your SELL-first preference if there’s a main leg; otherwise natural order
            if has_main_leg_for_exit(basket):
                legs = sorted(legs, key=lambda lg: 0 if lg.action == 'S' else 1)

            ptype = ptype_override or 'market'

            # Idempotent loop: act only on legs that still have quantity
            for leg in legs:
                if leg.status == 'exited' or not leg.quantity or leg.quantity <= 0:
                    continue
                qty = int(leg.quantity or 0)
                safe_compute_and_assign(leg, qty, ptype, exit_reason)
                leg.status = 'exited'
                leg.exited_at = datetime.now()
                leg.quantity = 0

            # If all legs exited, close basket
            all_exited_now = all((lg.status == 'exited') for lg in basket.legs)
            if all_exited_now:
                basket.status = 'exited'
                basket.exited_at = datetime.now()
                basket.exit_reason = exit_reason

            check_and_update_basket_alert_exit(basket, alert, exit_reason)
            message = 'All legs exited successfully'

            # 🔻 Fire the broker/exit pipeline only for the legs we actually touched
            orders_data = []
            scanner_id = basket.live_scanner_id
            if basket.strategy == 'custom':
                for leg in basket.legs:
                    # EQ legs only (kept from your code)
                    if leg.instrument_type == 'EQ' and (leg.exit_quantity or leg.exit_price):
                        instrument = leg.symbol
                        qty        = leg.exit_quantity or 0
                        price      = leg.exit_price or 0.0
                        run_in_thread(send_full_exit, instrument, scanner_id, price, qty, user_key)
            else:
                # Build orders only for legs where we have exit quantities/prices
                for leg in basket.legs:
                    if (leg.exit_quantity or 0) <= 0:
                        continue
                    instrument   = leg.symbol
                    qty          = int(leg.exit_quantity or 0)
                    price        = float(leg.exit_price or 0.0)
                    order_type   = 'BUY' if leg.action.upper().startswith('B') else 'SELL'
                    tradingsymbol = leg.symbol
                    limit_price   = price
                    expiry_date   = leg.expiry
                    try:
                        if leg.instrument_type in {'CE', 'PE'}:
                            token, symbol = get_instrument_token(
                                leg.symbol, expiry_date.strftime("%Y-%m-%d"), leg.strike, leg.instrument_type
                            )
                        elif leg.instrument_type == 'FUT':
                            token, symbol = get_instrument_token(
                                leg.symbol, expiry_date.strftime("%Y-%m-%d"), 0, leg.instrument_type
                            )
                        else:
                            token, symbol = None, leg.symbol  # EQ fallback

                        orders_data.append({
                            'trade_id':      scanner_id,
                            'trade_type':    order_type,
                            'tradingsymbol': tradingsymbol,
                            'limit_price':   limit_price,
                            'lots':          qty,
                            'optionsymbol':  symbol,
                            'alert_id':      alert.session_user
                        })
                    except Exception as e:
                        import traceback
                        print(f"❌ Error processing leg {leg.symbol}:", traceback.format_exc())
                        # don’t raise → continue building what we can

                if orders_data:
                    try:
                        run_in_thread(verify_trades_data, orders_data, user_key)
                    except Exception as e:
                        import traceback
                        print(f"❌ Error in verify_trades_data:", traceback.format_exc())
                        # swallow and proceed

        # SINGLE-LEG FULL EXIT
        else:
            if leg_index is None:
                return jsonify({'success': False, 'message': 'leg_index required for single-leg exit'}), 400

            if leg_index < 0 or leg_index >= len(basket.legs):
                return jsonify({'success': False, 'message': 'Invalid leg_index'}), 400

            leg = basket.legs[leg_index]

            if leg.status == 'exited' or not leg.quantity or leg.quantity <= 0:
                return jsonify({'success': True, 'message': 'Leg already exited; nothing to do'}), 200

            qty   = int(leg.quantity or 0)
            ptype = ptype_override or (leg.premium_type or 'market')

            safe_compute_and_assign(leg, qty, ptype, exit_reason)
            leg.quantity = 0
            leg.status = 'exited'
            leg.exited_at = datetime.now()

            check_and_update_basket_alert_exit(basket, alert, exit_reason)
            message = 'Single leg fully exited successfully'

        db.session.commit()

        exit_type = ('Partial Exit' if is_partial else
                     'Exit All Legs' if exit_all else
                     'Single Leg Exit')

        try:
            generate_and_send_exit_email(alert, basket, exit_type)
        except Exception as e:
            import traceback
            print(f"❌ Error sending exit email:", traceback.format_exc())

        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'legs': [{'id': lg.id, 'symbol': lg.symbol, 'pnl': lg.pnl} for lg in basket.legs],
                'basket': basket.to_dict(),
                'alert': alert.to_dict()
            }
        }), 200

    except Exception as e:
        import traceback
        print("❌ CRITICAL ERROR IN exit_basket_legs:", traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Error exiting legs',
            'error': str(e),
            'error_type': e.__class__.__name__
        }), 500



# @app.route('/api/baskets/<int:basket_id>/exit-legs_all', methods=['POST']) 
# def exit_basket_legs(basket_id):
#     """Partial, single, or full exit of all legs in a basket."""
#     import threading

#     def run_in_thread(target, *args, **kwargs):
#         try:
#             t = threading.Thread(target=target, args=args, kwargs=kwargs)
#             t.daemon = True
#             t.start()
#         except Exception as e:
#             print(f"❌ Failed to start thread for {target.__name__}: {e}")

#     try:
#         basket = db.session.get(Basket, basket_id)
#         if not basket:
#             return jsonify({'success': False, 'message': 'Basket not found'}), 404
#         alert = db.session.get(Alert, basket.alert_id)
#         user_key = alert.session_user if alert else None
#         if not alert or alert.status != 'triggered':
#             return jsonify({
#                 'success': False,
#                 'message': 'Alert must be triggered to exit legs',
#                 'current_status': alert.status if alert else None
#             }), 400
#         data = request.get_json() or {}
#         is_partial     = data.get('is_partial_exit', False)
#         exit_all       = data.get('exit_all_legs', False)
#         leg_index      = data.get('leg_index')
#         exit_qty       = data.get('exit_quantity')
#         exit_reason    = data.get('exit_reason', 'Manual exit')
#         ptype_override = (data.get('exit_price_type') or '').lower()
#         if is_partial:
#             if leg_index is None or exit_qty is None:
#                 return jsonify({'success': False, 'message': 'leg_index and exit_quantity required'}), 400
#             leg = basket.legs[leg_index]
#             if exit_qty > leg.quantity:
#                 return jsonify({'success': False, 'message': 'Invalid exit_quantity'}), 400
#             ptype = ptype_override or leg.premium_type or 'market'
#             _compute_and_assign(leg, exit_qty, ptype, exit_reason)
#             leg.quantity -= exit_qty
#             if leg.quantity <= 0:
#                 leg.status    = 'exited'
#                 leg.exited_at = datetime.now()
#             check_and_update_basket_alert_exit(basket, alert, exit_reason)
#             message = 'Partial exit executed successfully'
#         elif exit_all:
#             legs = basket.legs
#             has_main = has_main_leg_for_exit(basket)
#             if has_main:
#                 sorted_legs = sorted(legs, key=lambda lg: 0 if lg.action == 'S' else 1)
#             else:
#                 sorted_legs = legs
#             for leg in sorted_legs:
#                 qty = leg.quantity
#                 ptype = ptype_override or 'market'
#                 _compute_and_assign(leg, qty, ptype, exit_reason)
#                 leg.status    = 'exited'
#                 leg.exited_at = datetime.now()
#                 leg.quantity  = 0
#             basket.status     = 'exited'
#             basket.exited_at  = datetime.now()
#             basket.exit_reason = exit_reason
#             check_and_update_basket_alert_exit(basket, alert, exit_reason)
#             message = 'All legs exited successfully'
#             orders_data = []
#             user_key = alert.session_user
#             scanner_id = basket.live_scanner_id
#             if basket.strategy == 'custom':
#                 for leg in basket.legs:
#                     if leg.instrument_type == 'EQ':
#                         instrument = leg.symbol
#                         qty        = leg.exit_quantity or 0
#                         price      = leg.exit_price or 0.0
#                         print((instrument, scanner_id, price, qty, user_key))
#                         # Run send_full_exit in a thread to avoid breaking API
#                         run_in_thread(send_full_exit, instrument, scanner_id, price, qty, user_key)
#             else:
#                 for leg in basket.legs:
#                     instrument = leg.symbol
#                     qty        = leg.exit_quantity or 0
#                     price      = leg.exit_price or 0.0
#                     order_type     = 'BUY' if leg.action.upper().startswith('B') else 'SELL'
#                     tradingsymbol  = leg.symbol
#                     limit_price    = price
#                     quantity       = qty
#                     expiry_date = leg.expiry
#                     try:
#                         if leg.instrument_type in {'CE', 'PE'}:
#                             token, symbol = get_instrument_token(leg.symbol, expiry_date.strftime("%Y-%m-%d"), leg.strike, leg.instrument_type)
#                         elif leg.instrument_type == 'FUT':
#                             token, symbol = get_instrument_token(leg.symbol, expiry_date.strftime("%Y-%m-%d"), 0, leg.instrument_type)
#                         order_data = {
#                             'trade_id':      scanner_id,
#                             'trade_type':    order_type,
#                             'tradingsymbol': tradingsymbol,
#                             'limit_price':   limit_price,
#                             'lots':          quantity,
#                             'optionsymbol':  symbol,
#                             'alert_id':      alert.session_user
#                         }
#                         orders_data.append(order_data)
#                     except Exception as e:
#                         import traceback
#                         print(f"❌ Error processing leg {leg.symbol}:", traceback.format_exc())
#                         raise
#                 try:
#                     print(orders_data, user_key)
#                     # Run verify_trades_data in a thread to avoid breaking API
#                     run_in_thread(verify_trades_data, orders_data, user_key)
#                 except Exception as e:
#                     import traceback
#                     print(f"❌ Error in verify_trades_data:", traceback.format_exc())
#                     # Do not raise, just log
#         else:
#             if leg_index is None:
#                 return jsonify({'success': False, 'message': 'leg_index required for single-leg exit'}), 400
#             leg = basket.legs[leg_index]
#             qty = leg.quantity
#             ptype = ptype_override or leg.premium_type or 'market'
#             _compute_and_assign(leg, qty, ptype, exit_reason)
#             leg.quantity  = 0
#             leg.status    = 'exited'
#             leg.exited_at = datetime.now()
#             check_and_update_basket_alert_exit(basket, alert, exit_reason)
#             message = 'Single leg fully exited successfully'
#         db.session.commit()
#         exit_type = (
#             'Partial Exit' if is_partial else
#             'Exit All Legs' if exit_all else
#             'Single Leg Exit'
#         )
#         try:
#             generate_and_send_exit_email(alert, basket, exit_type)
#         except Exception as e:
#             import traceback
#             print(f"❌ Error sending exit email:", traceback.format_exc())
#         response_data = {
#             'success': True,
#             'message': message,
#             'data': {
#                 'legs': [
#                     {'id': lg.id, 'symbol': lg.symbol, 'pnl': lg.pnl}
#                     for lg in basket.legs
#                 ],
#                 'basket': basket.to_dict(),
#                 'alert': alert.to_dict()
#             }
#         }
#         return jsonify(response_data), 200
#     except Exception as e:
#         import traceback
#         import threading
#         print("❌ CRITICAL ERROR IN exit_basket_legs:", traceback.format_exc())
#         db.session.rollback()
#         return jsonify({
#             'success': False,
#             'message': 'Error exiting legs',
#             'error': str(e),
#             'error_type':  e.__class__.__name__
#         }), 500


        


@app.route('/api/baskets/<int:basket_id>/exit', methods=['POST'])
def exit_basket(basket_id):
    """Exit a basket (close all positions)"""
    try:
        basket = Basket.query.get(basket_id)
        
        if not basket:
            return jsonify({
                'error': 'Basket not found',
                'basket_id': basket_id
            }), 404
        
        if basket.status != 'active':
            return jsonify({
                'error': 'Cannot exit basket',
                'message': 'Only active baskets can be exited',
                'current_status': basket.status
            }), 400
        
        data = request.get_json() or {}
        
        # Update basket status
        basket.status = 'exited'
        basket.exited_at = datetime.now()
        basket.exit_reason = data.get('exit_reason', 'Manual exit')
        
        # Exit all legs in the basket
        for leg in basket.legs:
            if leg.status != 'exited':
                leg.status = 'exited'
                leg.exited_at = datetime.now()
        
        # db.session.commit()
        
        return jsonify({
            'basket': basket.to_dict(),
            'message': 'Basket exited successfully',
            'status': 'success'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to exit basket',
            'message': str(e)
        }), 500

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Resource not found',
        'message': 'The requested endpoint does not exist'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        'error': 'Bad request',
        'message': 'Invalid request data'
    }), 400









# Add these new endpoints to your existing Flask backend

# ========================================
# MARKET DATA ENDPOINTS
# ========================================


def get_all_banknifty_instruments():
    url = 'https://api.kite.trade/instruments'
    csv_filename = 'instruments.csv'
    response = requests.get(url)
    if response.status_code == 200:
        temp_filename = 'temp_instruments.csv'
        with open(temp_filename, 'wb') as file:
            file.write(response.content)
        instrumentList = pd.read_csv(temp_filename)
        filtered_instruments = instrumentList
        if os.path.exists(csv_filename):
            os.remove(csv_filename)
            print(f"Existing file '{csv_filename}' deleted.")
        filtered_instruments.to_csv(csv_filename, index=False)
        print(f"Filtered data saved to '{csv_filename}'.")
        os.remove(temp_filename)
    else:
        print(f"Failed to download CSV. Status code: {response.status_code}")

get_all_banknifty_instruments()





@app.route("/get_price_db", methods=["GET"])
def get_price():
    symbol = request.args.get("symbol")
    # print (symbol)
    if symbol == "NIFTY 50":
        symbol = "NIFTY"
    if not symbol:
        return jsonify({'error': 'Instrument not provided'}), 400
    # primary_data = fetch_data(f"select price from  live_tick_{symbol.lower()} order by time desc limit 1;")

    # if primary_data:
    #     ltp = primary_data[0][0]
    # else:
    #     fallback_sql  = f"SELECT price FROM tick_{symbol.lower()} ORDER BY date DESC LIMIT 1;"
    #     ltp = fetch_data(fallback_sql)[0][0]

    # print(ltp)
    return jsonify({'price': 0})



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


def get_lot_size_only():
    """Fetch lot size for all instruments"""
    try:
        lot_sizes = instrument_df[['tradingsymbol', 'lot_size']].drop_duplicates()
        return lot_sizes.set_index('tradingsymbol')['lot_size'].to_dict()
    except Exception as e:
        print(f"Error fetching lot sizes: {str(e)}")
        return {}







@app.route('/api/get_lot_size', methods=['POST'])
def get_lot_size():
    data = request.get_json()
    symbol = data.get('symbol', '')
    instrument_type = data.get('instrument_type', '')

    # Log incoming request for debugging
    print(f"Received lot size request for symbol: {symbol}, instrument type: {instrument_type}")

    # Filter your DataFrame
    df = filter_instruments(name=symbol, instrument_type=instrument_type)
    if df.empty:
        return jsonify({'error': 'Symbol not found'}), 404

    # Extract and cast to plain int
    lot_size_np = df.iloc[0]['lot_size']
    lot_size = int(lot_size_np)

    return jsonify({'lot_size': lot_size})




@app.route('/api/symbols', methods=['GET'])
def get_symbols():
    try:
        rename_map = {'NIFTY 50': 'NIFTY', 'NIFTY BANK': 'BANKNIFTY'}
        allowed_exchanges = ['NFO', 'NSE']

        # Filter out rows where 'name' is empty or null before other operations
        filtered_df = (
            instrument_df
            .loc[instrument_df['name'].notnull() & (instrument_df['name'] != '')]
            .loc[instrument_df['exchange'].isin(allowed_exchanges)]
            .replace({'name': rename_map, 'tradingsymbol': rename_map})
            .rename(columns={'tradingsymbol': 'symbol'})
            .assign(symbol=lambda df: df['symbol'].fillna(''))
        )

        response = (
            filtered_df[['symbol', 'instrument_type', 'name','segment','lot_size']]
            .drop_duplicates()
            .to_dict(orient='records')
        )

        return jsonify({
            'symbols': {'all_symbols': response},
            'status': 'success'
        })

    except Exception as e:
        print(f"Error in get_symbols: {str(e)}")  # Debug logging
        return jsonify({
            'error': 'Failed to fetch symbols',
            'message': str(e)
        }), 500




@app.route('/api/expiries/<symbol>', methods=['GET'])
def get_expiries(symbol):
    print(f"Getting expiries for symbol: {symbol}")
    try:
        # normalize certain names
        sym_up = symbol.upper()
        if sym_up in ['NIFTY 50', 'NIFTY']:
            symbol = 'NIFTY'
        elif sym_up in ['NIFTY BANK', 'BANKNIFTY']:
            symbol = 'BANKNIFTY'

        # pull instrument_type from querystring
        print (f"Fetching expiries for symbol: {symbol}", f"instrument_type: {request.args.get('instrument_type')}")
        instrument_type = request.args.get('instrument_type', '').upper()
        if instrument_type not in VALID_TYPES:
            return jsonify({
                'error': 'Missing or invalid instrument_type',
                'message': f'instrument_type must be one of {sorted(VALID_TYPES)}'
            }), 400

        # filter by both symbol AND instrument_type
        filtered_data = filter_instruments(name=symbol, instrument_type=instrument_type)

        if filtered_data.empty:
            return jsonify({
                'error': 'No data found',
                'message': f'No expiries found for {symbol} ({instrument_type})'
            }), 404

        expiries = sorted(
            filtered_data['expiry']
            .dropna()
            .astype(str)
            .unique().tolist()
        )
        print(f"Found {len(expiries)} expiries for {instrument_type}: {expiries[:3]}...")

        # you can calculate current_price here if you want
        current_price = None

        return jsonify({
            'symbol': symbol.upper(),
            'instrument_type': instrument_type,
            'expiries': expiries,
            'total_expiries': len(expiries),
            'current_price': current_price,
            'status': 'success'
        })

    except Exception as e:
        print(f"Error in get_expiries: {e}")
        return jsonify({
            'error': 'Failed to fetch expiries',
            'message': str(e)
        }), 500





def fetch_option_chain_data(symbol: str, expiry: str, instrument_type: str = 'CE') -> pd.DataFrame:
    print("Fetching option chain:", symbol, expiry, instrument_type)
    getting_lot = filter_instruments(symbol, expiry,instrument_type)
    # Convert expiry to required format: 'YYYY-MM-DD' -> 'DD-MMM-YYYY'
    expiry_fmt = datetime.strptime(expiry, '%Y-%m-%d').strftime('%d-%b-%Y')

    is_index = symbol.upper() in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
    home_url = 'https://www.nseindia.com/option-chain'
    api_url = f'https://www.nseindia.com/api/option-chain-{"indices" if is_index else "equities"}?symbol={symbol.upper()}'

    headers = {
        'authority': 'www.nseindia.com',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'referer': 'https://www.nseindia.com/option-chain',
    }

    session = requests.Session()

    # First call to home_url to set cookies
    init_resp = session.get(home_url, headers=headers)
    print("Init status:", init_resp.status_code)

    # Now call API
    response = session.get(api_url, headers=headers)
    print("API status:", response.status_code)

    if response.status_code != 200:
        print("❌ Failed to fetch data. Status:", response.status_code)
        print(response.text[:500])  # print first 500 chars for debugging
        return pd.DataFrame()

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        print("❌ Response is not JSON. Response text:")
        print(response.text[:500])
        return pd.DataFrame()

    records = data.get('records', {}).get('data', [])
    filtered_data = []
    for item in records:
        if item.get("expiryDate") != expiry_fmt:
            continue
        if instrument_type not in item:
            continue

        option_data = item[instrument_type]
        prev_oi = option_data['openInterest'] - option_data['changeinOpenInterest']
        oi_change_percent = (option_data['changeinOpenInterest'] / prev_oi * 100) if prev_oi else 0

        filtered_data.append({
            'strikes':           int(item['strikePrice']),
            'expiry':            expiry_fmt,
            'oi':                int(option_data['openInterest']),
            'oi_change':         int(option_data['changeinOpenInterest']),
            'oi_change_percent': float(round(oi_change_percent, 2)),
            'ltp':               float(option_data['lastPrice']),
            'lot_size':        int(getting_lot['lot_size'].iloc[0])  # Uncomment if you have getting_lot defined here
        })

    df = pd.DataFrame(filtered_data).sort_values(by='strikes')
    return df





# @app.route('/api/strikes/<symbol>/<expiry>/<instrument_type>', methods=['GET'])
@app.route('/api/option-chain', methods=['POST'])
def get_option_chain():
    try:
        # Parse input JSON
        data = request.json
        symbol = data.get('symbol')
        expiry = data.get('expiry')
        instrument_type = data.get('instrument_type', 'CE').upper()

        if not symbol or not expiry:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameters: symbol or expiry'
            }), 400

        # Fetch option chain data using your existing function
        
        df = fetch_option_chain_data(symbol, expiry, instrument_type)
        current_price = 0
        # print (df.to_dict(orient='records'))
        # Get sample lot size from the first row to use as global lot size
        try:
            lot_size = df.iloc[0]['lot_size'] if not df.empty else 0
        except:
            lot_size = 0
            

        # Format the response according to what the frontend expects
        return jsonify({
            'status': 'success',
            'strikes': df.to_dict(orient='records'),
            'current_price': current_price,
            'lot_size': int(lot_size)
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500




# ── MAP “underlying” names to Kite Connect keys ────────────────────────────
INDEX_KEY_MAP = {
    "NIFTY":     "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK"
}

@app.route('/api/symbol-live-data', methods=['POST'])
def symbol_live_data():
    data = request.get_json() or {}
    symbol = data.get('instrument', '').upper()

    if not symbol:
        return jsonify({"error": "No instrument provided"}), 400 

    # pick from our index map, or default to NSE:<symbol>
    kite_key = INDEX_KEY_MAP.get(symbol, f"NSE:{symbol}")

    try:   
        ltp_data = kite.ltp([kite_key])
        last_price = ltp_data[kite_key]['last_price']
        return jsonify({'ltp': last_price})
    except Exception as e:
        print("[LTP Error]", e)
        return jsonify({'error': str(e)}), 500



    
    
VALID_TYPES = {'EQ', 'FUT', 'CE', 'PE'}
@app.route('/api/get-live-data', methods=['POST'])
def get_live_data():
    data = request.get_json() or {}
    symbol = data.get('symbol')
    expiry = data.get('expiry')
    strike = data.get('strike')
    instrument_type = data.get('instrument_type')

    # 1) instrument_type must itself be present and valid
    if instrument_type not in VALID_TYPES:
        return jsonify({'error': 'instrument_type is missing or invalid'}), 400

    # 2) build a list of required fields based on type
    required = ['symbol']
    if instrument_type in {'CE', 'PE'}:
        required += ['expiry', 'strike']
    elif instrument_type == 'FUT':
        required += ['expiry']
    # for 'EQ' only symbol is required

    # 3) check which ones are actually missing/empty
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({
            'error': 'Missing required fields for ' + instrument_type,
            'missing': missing
        }), 400

    try:
        # now you can safely call get_instrument_token with the right parameters
        if instrument_type in {'CE', 'PE'}:
            token,trading_symbol = get_instrument_token(symbol, expiry, strike, instrument_type)
        elif instrument_type == 'FUT':
            token,trading_symbol = get_instrument_token(symbol, expiry, 0, instrument_type)
        else:  # EQ
            token,trading_symbol = get_instrument_token(symbol, '', 0, 'EQ')
            print ("EQ token:", token)

        if not token:
            return jsonify({'error': f"Token not found for {instrument_type}"}), 404

        ltp_data   = kite.ltp    ([token])
        depth_data = kite.quote  ([token])

        ltp      = ltp_data   [str(token)]['last_price']
        depth    = depth_data [str(token)]['depth']
        best_bid = depth['buy'][0]['price']  if depth['buy']  else 0
        best_ask = depth['sell'][0]['price'] if depth['sell'] else 0
        mid = round((best_bid + best_ask) / 2, 2) if best_bid and best_ask else ltp

        return jsonify({
            'symbol': symbol,
            'expiry': expiry,
            'strike': strike,
            'instrument_type': instrument_type,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid,
            'depth': {
                'bids': depth['buy'],
                'asks': depth['sell']
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# token = 128083204

# ltp_data   = kite.ltp    ([token])
# depth_data = kite.quote  ([token])
# ltp      = ltp_data   [str(token)]['last_price']
# depth    = depth_data [str(token)]['depth']
# best_bid = depth['buy'][0]['price']  if depth['buy']  else 0
# best_ask = depth['sell'][0]['price'] if depth['sell'] else 0
# mid = round((best_bid + best_ask) / 2, 2) if best_bid and best_ask else ltp
# print("LTP:", ltp)
# print("Best Bid:", best_bid)
# print("Best Ask:", best_ask)
# print("Mid Price:", mid)    
# exit(0)

@app.route('/api/get-basket-margin', methods=['POST'])
def get_basket_margin():
    data = request.get_json() or {}
    legs = data.get('legs')
    if not isinstance(legs, list) or not legs:
        return jsonify({'error': 'Request must include a non-empty "legs" array'}), 400

    eq_cal = []
    order_payload = []
    for leg in legs:
        # print(legs)
        action = leg.get('action') or ''
        itype  = leg.get('instrument_type') or ''
        qty    = int(leg.get('quantity') or 0)
        symbol = leg.get('symbol') or ''
        expiry = leg.get('expiry') or ''
        strike = float(leg.get('strike') or 0)
        
        # validation
        if not all([action, itype, qty, symbol]):
            return jsonify({'error': f'Missing required fields in leg: {leg}'}), 400
        if itype in ('CE', 'PE', 'FUT') and not expiry:
            return jsonify({'error': f'Expiry is required for {itype} leg: {leg}'}), 400
        if itype in ('CE', 'PE') and not strike:
            return jsonify({'error': f'Strike is required for option leg: {leg}'}), 400

        # lookup token, tradingsymbol, lot
        ts = ''
        
        try:
            if itype == 'CE' or itype == 'PE':
                token,tradingsymbol = get_instrument_token(symbol, expiry, strike, itype)
                row = instrument_df[instrument_df['instrument_token'] == token]
                if row.empty:
                    raise ValueError()
                ts  = row.iloc[0]['tradingsymbol']
                lot = int(row.iloc[0].get('lot_size') or row.iloc[0].get('lot') or 1)
            elif itype == 'FUT':
                token,tradingsymbol = get_instrument_token(symbol=symbol, expiry=expiry, strike=None, instrument_type="FUT")
                row = instrument_df[instrument_df['instrument_token'] == token]
                if row.empty:
                    raise ValueError()
                ts = row.iloc[0]['tradingsymbol']
                lot = int(row.iloc[0].get('lot_size') or row.iloc[0].get('lot') or 1)
            elif itype == 'EQ':
                token,tradingsymbol = get_instrument_token(symbol=symbol, expiry=None, strike=None, instrument_type="EQ")
                row = instrument_df[instrument_df['instrument_token'] == token]
                if row.empty:
                    raise ValueError()
                
                lot = int(row.iloc[0].get('lot_size'))
                tradingsymbol = row.iloc[0].get('tradingsymbol')
                # print(leg['premium'])
                price = leg['premium']
                quantity = leg['quantity']
                print(quantity, price)
                eq_cal.append({'tradingsymbol': tradingsymbol, 'quantity': quantity,'premium':price, 'price': leg['price']})
            else:
                raise ValueError()
        except Exception:
            return jsonify({'error': f'Instrument not found: {symbol} {expiry} {strike}'}), 404

       

        exchange = 'NFO' if itype in ('CE', 'PE','FUT') else 'NSE'
        order_payload.append({
            "exchange": exchange,
            "tradingsymbol": ts if ts else "",
            "transaction_type": "BUY" if action == "B" else "SELL",
            "quantity": qty,
            "variety": "regular",
            "product": "NRML",
            "order_type": "MARKET",
            "price": 0,
            "trigger_price": 0
        })

    def sum_per_order_margins(payload):
        resp = kite.order_margins(payload, mode="compact")
        data = resp.get('data', [])
        total = sum(item.get('total', 0) for item in data)
        return {'total_margin': total, 'orders': data}
    
    if eq_cal:
        print ("## Calculating margins for EQ legs")
        margins = []
        for item in eq_cal:
            try:
                sum_r = item['premium'] * item['quantity']
            except Exception as e:
                sum_r = item['price'] * item['quantity']
                
        req_margin = sum_r
        blk_margin = 0
        result = ({
        'required_margin': round(req_margin),
        'blocked_margin':  round(blk_margin),
        'legs':            margins
        })
        # print(order_payload)
        print (blk_margin,req_margin)   
        return result
    
    if order_payload:
        try:
            # print (order_payload)
            # single call for the entire basket
            margins = kite.basket_order_margins(order_payload)
        except Exception as e:
            print("[ERROR in basket margins]", e)
            return jsonify({'error': str(e)}), 500

        # margins may be either a list of OrderMargins OR a dict with 'initial','final','orders'
        if isinstance(margins, dict) and 'initial' in margins:
            req_margin = margins['initial'].get('total', 0)
            blk_margin = margins['final'].get('total', 0)
        else:
            # fallback: sum the .total of each returned margin object
            req_margin = sum(m.get('total',0) for m in margins)
            blk_margin = req_margin
    else:
        margins = []
        req_margin = 0
        blk_margin = 0

    
    result = ({
        'required_margin': round(req_margin),
        'blocked_margin':  round(blk_margin),
        'legs':            margins
    })
    print(order_payload)
    print (blk_margin,req_margin)
    return result


@app.route("/alert_triggers_order")
def home():
    return render_template("index.html")


# ========================================
# MAIN APPLICATION
# ========================================

if __name__ == '__main__':
    # # Create tables on startup
    # create_tables()
    
    # # Initialize sample data (optional)
    # # init_sample_data()
    
    # # Run the app
    print("Starting Advanced ATO Basket Builder API...")
    print("API Documentation available at: http://192.168.4.221:9000/")
    print("Health check: http://192.168.4.221:9000/api/health")
    app.run(debug=False, host='0.0.0.0', port=9000)


