# =======================
# Standard Library Imports
# =======================
# python -m celery -A websocket_server worker --loglevel=info --pool=threads --concurrency=5 --loglevel=info
 
import time
import json
import sqlite3
import logging
from datetime import datetime

# =======================
# Third-Party Imports
# =======================
import pandas as pd
import redis
import requests
from celery import Celery
from kiteconnect import KiteConnect

# =======================
# Constants and Configs
# =======================
DB_PATH          = r"C:\Users\Alkalyme\Downloads\ato_project\ato_project\instance\ato_system.db"
INSTRUMENT_CSV   = r"C:\Users\Alkalyme\Downloads\ato_project\ato_project\instruments.csv"
REDIS_HOST       = "127.0.0.1"
REDIS_PORT       = 6379
TICK_SERVICE_URL = "http://localhost:5000/ticks"

# =======================
# Load Instrument Data
# =======================
instrument_df = pd.read_csv(INSTRUMENT_CSV)
instrument_df = instrument_df[instrument_df['exchange'].isin(['NSE','NFO'])].reset_index(drop=True)

# =======================
# Redis Setup
# =======================
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# =======================
# Kite Connect Setup
# =======================
access_token_path = r'\\Velocity\c\Users\kunal\Downloads\LIVE_TICK_HIGH_LOW_FLASK\LIVE_TICK_HIGH_LOW_FLASK\zerodha_access_token.txt'
access_token = open(access_token_path).read().strip()
kite = KiteConnect(api_key="zuuxkho8imp70m8c", access_token=access_token)

# =======================
# Celery Setup
# =======================
celery = Celery(
    'websocket_server',
    broker=f'redis://{REDIS_HOST}:{REDIS_PORT}/0',
    backend=f'redis://{REDIS_HOST}:{REDIS_PORT}/0',
    include=['websocket_server']
)

# ====================================================================
# UTILITIES (UNCHANGED)
# ====================================================================


def is_before_valid_till(valid_till_str: str) -> bool:
    """Return True if now is before (or equal to) valid_till."""
    try:
        valid_dt = datetime.fromisoformat(valid_till_str.replace("Z", "+00:00"))
        return datetime.now() <= valid_dt
    except Exception as e:
        print ("trade is expired")
        return False

def get_instrument_id(symbol: str) -> int:
    """Lookup the instrument_token for a given trading symbol."""
    try:
        if symbol == "NIFTY":
            symbol = "NIFTY 50"
        return int(instrument_df.loc[instrument_df["tradingsymbol"] == symbol, "instrument_token"].iloc[0])
    except Exception as e:
        raise ValueError(f"Instrument '{symbol}' not found in CSV") from e

def compare(a: float, operator: str, b: float) -> bool:
    """Compare a and b with the given operator."""
    if operator == ">=":
        return a >= b
    elif operator == ">":
        return a > b
    elif operator == "<=":
        return a <= b
    elif operator == "<":
        return a < b
    elif operator == "==":
        return a == b
    elif operator == "!=":
        return a != b
    else:
        raise ValueError(f"Unsupported operator '{operator}'")

def calculate_leg_pnl(leg, current_premium):
    """
    Calculates PnL for an individual leg.
    For short position: PnL = (entry_premium - current_premium) * qty * lot_size
    """
    if current_premium is None:
        return 0

    entry_premium = leg['entry_premium']
    qty           = leg['quantity']
    lot_size      = 1  # set to 50 if qty is in lots for NIFTY

    if leg['action'] == 'S':  # Short
        pnl = (entry_premium - current_premium) * qty * lot_size
    elif leg['action'] == 'B':  # Long
        pnl = (current_premium - entry_premium) * qty * lot_size
    else:
        pnl = 0

    return pnl

# ====================================================================
# NEW: BASKET STATE MANAGEMENT FUNCTIONS
# ====================================================================
def check_basket_status_in_db(basket_id: int, cur) -> bool:
    """
    Check if basket is still active in database.
    Returns True if basket should continue to be monitored.
    """
    try:
        cur.execute("SELECT status FROM baskets WHERE id = ?", (basket_id,))
        result = cur.fetchone()
        
        if not result:
            print(f"⚠️ Basket {basket_id} not found in database")
            return False
            
        status = result[0]
        # Add your actual status values here
        active_statuses = ['active', 'open', 'monitoring', 'triggered']
        inactive_statuses = ['exited', 'closed', 'completed', 'stopped']
        
        if status in inactive_statuses:
            print(f"📋 Basket {basket_id} status: {status} - marking as inactive")
            return False
        elif status in active_statuses:
            return True
        else:
            print(f"⚠️ Basket {basket_id} unknown status: {status} - continuing monitoring")
            return True
            
    except Exception as e:
        print(f"❌ Error checking basket {basket_id} status: {e}")
        return True  # Continue monitoring on error

def update_basket_exit_status_in_db(basket_id: int, cur, conn, reason: str = "Auto exit"):
    """
    Update basket status in database when exited through risk management.
    """
    try:
        cur.execute("""
            UPDATE baskets 
            SET status = 'exited', 
                exit_time = ?,
                exit_reason = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), reason, basket_id))
        conn.commit()
        print(f"📋 Updated basket {basket_id} status to 'exited' in database")
    except Exception as e:
        print(f"❌ Error updating basket {basket_id} exit status: {e}")

# ====================================================================
# UPDATED: API CALL FUNCTION
# ====================================================================
API_BASE = "http://localhost:5000/api"

def call_exit_api(
    basket_id: int,
    is_partial: bool,
    exit_all: bool,
    leg_index: int = None,
    exit_qty: int = None,
    reason: str = "Auto exit",
    price_type: str = "market"
) -> dict:
    """
    Helper to call the single/partial/full exit API.
    Returns True if exit was successful, False otherwise.
    """
    # Convert basket_id to string for URL
    url = f"http://192.168.4.221:9000/api/baskets/{str(basket_id)}/exit-legs_all"
    payload = {
        "is_partial_exit":  is_partial,
        "exit_all_legs":    exit_all,
        "exit_reason":      reason,
        "exit_price_type":  price_type
    }
    
    if not exit_all:
        if leg_index is None or exit_qty is None:
            raise ValueError("leg_index and exit_qty required for single/partial exit")
        payload.update({
            "leg_index":     leg_index,
            "exit_quantity": exit_qty
        })

    print(f"🛑 CALLING EXIT API:")
    print(f"   URL: {url}")
    print(f"   Payload: {payload}")

    try:
        resp = requests.post(url, json=payload, timeout=30)  # Add timeout
        resp.raise_for_status()
        result = resp.json()
        # print(f"   ✅ EXIT API SUCCESS: {result}")
        return {"success": True, "data": result}
    except Exception as e:
        print(f"   ❌ EXIT API ERROR: {e}")
        return {"success": False, "error": str(e)}

# ====================================================================
# UPDATED: INDIVIDUAL LEG RISK MANAGEMENT (RETURNS EXIT STATUS)
# ====================================================================
def check_individual_leg_risk(basket_id, trade, current_leg_prices, cur, conn):
    """
    Individual leg risk management function.
    
    UPDATED: Now returns True if any leg was exited, False otherwise.
    This allows the main loop to track basket state properly.
    """
    
    # Get risk settings to determine which risk type to apply
    cur.execute("""
        SELECT option_type, is_active
        FROM risk_settings 
        WHERE basket_id = ? AND risk_type = 'individual' AND is_active = 1
    """, (basket_id,))
    
    risk_settings = cur.fetchall()
    
    if not risk_settings:
        print(f"   ⚠️ No active individual risk settings found for basket {basket_id}")
        return False
    
    # Get the option_type
    option_type = risk_settings[0][0]
    print(f"   🔧 Risk Type: {option_type}")
    
    exit_triggered = False  # Track if any leg was exited
    
    for idx, leg in enumerate(trade["legs"]):
        leg_id = leg["leg_id"]
        instr = leg.get("instrument_type", "").upper()
        
        # Pick entry based on instrument type
        if instr in ("EQ", "FUT"):
            entry = leg.get("entry_price", leg.get("entry_premium", 0.0))
        else:
            entry = leg.get("entry_premium", leg.get("entry_price", 0.0))
        
        print(f"   📍 Entry Price: {entry}")
        qty = leg.get("qty", leg.get("quantity", 0))
        action = leg["action"]
        margin = leg.get("margin", 0) or 0
        current = current_leg_prices.get(leg_id)
        
        if current is None:
            print(f"⚠️ Leg {leg_id}: No current price available")
            continue
            
        print(f"🦵 Checking Leg {leg_id}: {action} {qty} | Entry: {entry} | Current: {current}")

        # Get TP/SL values from legs table for this specific leg
        cur.execute("SELECT tp, sl FROM legs WHERE id = ?", (leg_id,))
        leg_data = cur.fetchone()
        
        if not leg_data:
            print(f"   ⚠️ Leg {leg_id}: No leg data found")
            continue
            
        tp_value, sl_value = leg_data
        
        if tp_value is None and sl_value is None:
            print(f"   ℹ️ Leg {leg_id}: No TP/SL configured - monitoring only")
            continue
            
        print(f"   📊 Leg TP/SL Values: TP={tp_value} | SL={sl_value}")
        print(f"   🔧 Applying risk type: {option_type}")
        
        # =================================================================
        # DYNAMIC RISK CALCULATION BASED ON OPTION_TYPE
        # =================================================================
        leg_exit_triggered = False  # Track this specific leg's exit
        
        if option_type == 'percentage':
            if action == 'B':  # Long position
                change_pct = ((current - entry) / entry) * 100
            else:  # Short position
                change_pct = ((entry - current) / entry) * 100
                
            print(f"   📈 Percentage Change: {change_pct:.2f}%")
            
            # Check TP condition
            if tp_value is not None and change_pct >= tp_value:
                print(f"   🎯 [PctTP] Leg {leg_id}: {change_pct:.2f}% ≥ TP {tp_value}%")
                api_result = call_exit_api(basket_id, False, False, 
                             leg_index=idx, exit_qty=qty,
                             reason="Individual TP Hit (Percentage)", 
                             price_type="market")
                leg_exit_triggered = api_result.get("success", False)
            
            # Check SL condition
            elif sl_value is not None and change_pct <= -abs(sl_value):
                print(f"   🛑 [PctSL] Leg {leg_id}: {change_pct:.2f}% ≤ SL -{sl_value}%")
                api_result = call_exit_api(basket_id, False, False, 
                             leg_index=idx, exit_qty=qty,
                             reason="Individual SL Hit (Percentage)", 
                             price_type="market")
                leg_exit_triggered = api_result.get("success", False)
            else:
                print(f"   ✅ [PctOK] Leg {leg_id}: Within {tp_value}%/{sl_value}% limits")
            
        elif option_type == 'points':
            if action == 'B':  # Long position
                point_change = current - entry
            else:  # Short position
                point_change = entry - current
                
            print(f"   📊 Point Change: {point_change:.2f}")
            
            # Check TP condition
            if tp_value is not None and point_change >= tp_value:
                print(f"   🎯 [PtTP] Leg {leg_id}: {point_change:.2f} ≥ TP {tp_value}")
                api_result = call_exit_api(basket_id, False, False, 
                             leg_index=idx, exit_qty=qty,
                             reason="Individual TP Hit (Points)", 
                             price_type="market")
                leg_exit_triggered = api_result.get("success", False)
            
            # Check SL condition
            elif sl_value is not None and point_change <= -abs(sl_value):
                print(f"   🛑 [PtSL] Leg {leg_id}: {point_change:.2f} ≤ SL -{sl_value}")
                api_result = call_exit_api(basket_id, False, False, 
                             leg_index=idx, exit_qty=qty,
                             reason="Individual SL Hit (Points)", 
                             price_type="market")
                leg_exit_triggered = api_result.get("success", False)
            else:
                print(f"   ✅ [PtOK] Leg {leg_id}: Within {tp_value}/{sl_value} point limits")
            
        elif option_type == 'premium':
            print(f"   💰 Premium Price Check")
            
            if action == 'B':  # Long position
                if tp_value is not None and current >= tp_value:
                    print(f"   🎯 [PrmTP] Leg {leg_id}: price {current} ≥ TP {tp_value}")
                    api_result = call_exit_api(basket_id, False, False, 
                                 leg_index=idx, exit_qty=qty,
                                 reason="Individual TP Hit (Premium)", 
                                 price_type="market")
                    leg_exit_triggered = api_result.get("success", False)
                
                elif sl_value is not None and current <= sl_value:
                    print(f"   🛑 [PrmSL] Leg {leg_id}: price {current} ≤ SL {sl_value}")
                    api_result = call_exit_api(basket_id, False, False, 
                                 leg_index=idx, exit_qty=qty,
                                 reason="Individual SL Hit (Premium)", 
                                 price_type="market")
                    leg_exit_triggered = api_result.get("success", False)
                    
            else:  # Short position
                if tp_value is not None and current <= tp_value:
                    print(f"   🎯 [PrmTP] Leg {leg_id}: price {current} ≤ TP {tp_value}")
                    api_result = call_exit_api(basket_id, False, False, 
                                 leg_index=idx, exit_qty=qty,
                                 reason="Individual TP Hit (Premium)", 
                                 price_type="market")
                    leg_exit_triggered = api_result.get("success", False)
                
                elif sl_value is not None and current >= sl_value:
                    print(f"   🛑 [PrmSL] Leg {leg_id}: price {current} ≥ SL {sl_value}")
                    api_result = call_exit_api(basket_id, False, False, 
                                 leg_index=idx, exit_qty=qty,
                                 reason="Individual SL Hit (Premium)", 
                                 price_type="market")
                    leg_exit_triggered = api_result.get("success", False)
                    
            if not leg_exit_triggered:
                print(f"   ✅ [PrmOK] Leg {leg_id}: Within {tp_value}/{sl_value} price limits")
            
        elif option_type == 'pnl_amount':
            pnl = calculate_leg_pnl(leg, current)
            print(f"   💵 PnL Amount: ₹{pnl:.2f}")
            
            if tp_value is not None and pnl >= tp_value:
                print(f"   🎯 [PnLTP] Leg {leg_id}: PnL ₹{pnl:.2f} ≥ TP ₹{tp_value}")
                api_result = call_exit_api(basket_id, False, False, 
                             leg_index=idx, exit_qty=qty,
                             reason="Individual TP Hit (PnL Amount)", 
                             price_type="market")
                leg_exit_triggered = api_result.get("success", False)
            
            elif sl_value is not None and pnl <= -abs(sl_value):
                print(f"   🛑 [PnLSL] Leg {leg_id}: PnL ₹{pnl:.2f} ≤ SL -₹{sl_value}")
                api_result = call_exit_api(basket_id, False, False, 
                             leg_index=idx, exit_qty=qty,
                             reason="Individual SL Hit (PnL Amount)", 
                             price_type="market")
                leg_exit_triggered = api_result.get("success", False)
            else:
                print(f"   ✅ [PnLOK] Leg {leg_id}: Within ₹{tp_value}/{sl_value} PnL limits")
            
        elif option_type == 'pnl_margin':
            if margin > 0:
                pnl = calculate_leg_pnl(leg, current)
                pct = (pnl / margin) * 100
                print(f"   📊 PnL % of Margin: {pct:.2f}%")
                
                if tp_value is not None and pct >= tp_value:
                    print(f"   🎯 [PnL%TP] Leg {leg_id}: {pct:.2f}% ≥ TP {tp_value}%")
                    api_result = call_exit_api(basket_id, False, False, 
                                 leg_index=idx, exit_qty=qty,
                                 reason="Individual TP Hit (PnL % Margin)", 
                                 price_type="market")
                    leg_exit_triggered = api_result.get("success", False)
                
                elif sl_value is not None and pct <= -abs(sl_value):
                    print(f"   🛑 [PnL%SL] Leg {leg_id}: {pct:.2f}% ≤ SL -{sl_value}%")
                    api_result = call_exit_api(basket_id, False, False, 
                                 leg_index=idx, exit_qty=qty,
                                 reason="Individual SL Hit (PnL % Margin)", 
                                 price_type="market")
                    leg_exit_triggered = api_result.get("success", False)
                else:
                    print(f"   ✅ [PnL%OK] Leg {leg_id}: Within {tp_value}%/{sl_value}% margin limits")
            else:
                print(f"   ⚠️ [NoMargin] Leg {leg_id}: No margin data for percentage calculation")
                
        else:
            print(f"   ⚠️ [UnknownType] Unknown option_type: {option_type}")
            print(f"   💡 Expected one of: percentage, points, premium, pnl_amount, pnl_margin")

        # Track if any leg was exited
        if leg_exit_triggered:
            exit_triggered = True
            print(f"   ✅ Leg {leg_id}: EXIT TRIGGERED - marked for basket state update")

        print(f"   ✅ Leg {leg_id}: Risk check completed")

    print(f"📋 Individual risk check completed for basket {basket_id}")
    
    # If any leg was exited, update basket status in database
    if exit_triggered:
        update_basket_exit_status_in_db(basket_id, cur, conn, "Individual leg exit")
    
    return exit_triggered

# ====================================================================
# UPDATED: BASKET WIDE RISK MANAGEMENT (RETURNS EXIT STATUS)
# ====================================================================

def get_normalized_risk_values(risk_cfg, option_type):
    """
    FIXED: Normalize different key formats from frontend/database.
    Handles various key naming conventions for TP/SL values.
    """
    tp_val = None
    sl_val = None
    
    # Print for debugging
    print(f"🔍 Raw risk config: {risk_cfg}")
    print(f"🔍 Option type: {option_type}")
    
    if option_type == "net_pnl_tp_sl":
        # Keys could be: tp/sl, tpAmount/slAmount, or tpPnl/slPnl
        tp_val = (risk_cfg.get("tp") or 
                  risk_cfg.get("tpAmount") or 
                  risk_cfg.get("tpPnl"))
        sl_val = (risk_cfg.get("sl") or 
                  risk_cfg.get("slAmount") or 
                  risk_cfg.get("slPnl"))
                  
    elif option_type == "pnl_margin_percentage":
        # Keys could be: tp/sl, tpMarginPct/slMarginPct, or tpMargin/slMargin
        tp_val = (risk_cfg.get("tp") or 
                  risk_cfg.get("tpMarginPct") or 
                  risk_cfg.get("tpMargin"))
        sl_val = (risk_cfg.get("sl") or 
                  risk_cfg.get("slMarginPct") or 
                  risk_cfg.get("slMargin"))
                  
    elif option_type == "time_based":
        # Keys could be: tp/sl, tpTime/slTime, or exitTime/stopTime
        tp_val = (risk_cfg.get("tp") or 
                  risk_cfg.get("tpTime") or 
                  risk_cfg.get("exitTime"))
        sl_val = (risk_cfg.get("sl") or 
                  risk_cfg.get("slTime") or 
                  risk_cfg.get("stopTime"))
                  
    elif option_type == "points_based":
        # Keys could be: tp/sl, tpPoints/slPoints
        tp_val = (risk_cfg.get("tp") or 
                  risk_cfg.get("tpPoints"))
        sl_val = (risk_cfg.get("sl") or 
                  risk_cfg.get("slPoints"))
                  
    elif option_type == "price_based":
        # Keys could be: tp/sl, tpPrice/slPrice
        tp_val = (risk_cfg.get("tp") or 
                  risk_cfg.get("tpPrice"))
        sl_val = (risk_cfg.get("sl") or 
                  risk_cfg.get("slPrice"))
    
    # Convert to appropriate types
    try:
        tp = float(tp_val) if tp_val is not None else None
    except (ValueError, TypeError):
        print(f"⚠️ Invalid TP value: {tp_val}")
        tp = None
        
    try:
        sl = float(sl_val) if sl_val is not None else None
    except (ValueError, TypeError):
        print(f"⚠️ Invalid SL value: {sl_val}")
        sl = None
    
    print(f"🎯 Normalized values: TP={tp}, SL={sl}")
    
    return tp, sl

def check_basket_wide_risk_fixed(basket_id: int, trade: dict, current_leg_prices: dict, 
                          current_underlying_price: float, initial_underlying_price: float, 
                          total_margin: float, cur, conn) -> bool:
    """
    FIXED: Basket-wide risk management with proper key mapping.
    """
    risk_cfg = trade["risk"].get("basket", {})
    print(f"🔍 Raw risk_cfg: {risk_cfg}")
    
    if not risk_cfg:
        print("❌ No risk config found")
        return False
    
    # Get the option type
    option_type = risk_cfg.get("option_type")
    if not option_type:
        print(f"❌ No option_type specified for basket {basket_id}")
        return False
    
    # FIXED: Use normalized key mapping
    tp, sl = get_normalized_risk_values(risk_cfg, option_type)
    
    # Calculate total PnL
    total_pnl = 0.0
    for leg in trade["legs"]:
        lid = leg["leg_id"]
        price = current_leg_prices.get(lid)
        if price is not None:
            total_pnl += calculate_leg_pnl(leg, price)
            
    print(f"📊 Basket {basket_id} Analysis:")
    print(f"   Total PnL: ₹{total_pnl:.2f}")
    print(f"   Option Type: {option_type}")
    print(f"   TP: {tp}, SL: {sl}")
    print(f"   Total Margin: ₹{total_margin:.2f}")
    
    exit_triggered = False
    
    # Apply risk management based on option_type
    if option_type == "net_pnl_tp_sl":
        if tp is not None and total_pnl >= tp:
            print(f"🎯 [BasketWide][NetPnL] TP Hit: ₹{total_pnl:.2f} ≥ ₹{tp}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Net PnL TP: ₹{tp}")
            exit_triggered = api_result.get("success", False)
        elif sl is not None and total_pnl <= -abs(sl):
            print(f"🛑 [BasketWide][NetPnL] SL Hit: ₹{total_pnl:.2f} ≤ -₹{sl}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Net PnL SL: ₹{sl}")
            exit_triggered = api_result.get("success", False)
            
    elif option_type == "pnl_margin_percentage":
        if total_margin > 0:
            pct = (total_pnl / total_margin) * 100
            print(f"💹 [BasketWide][Margin%] Current PnL%: {pct:.2f}%")
            
            if tp is not None and pct >= tp:
                print(f"🎯 [BasketWide][Margin%] TP Hit: {pct:.2f}% ≥ {tp}%")
                api_result = call_exit_api(basket_id, False, True, reason=f"Margin TP: {tp}%")
                exit_triggered = api_result.get("success", False)
            elif sl is not None and pct <= -abs(sl):
                print(f"🛑 [BasketWide][Margin%] SL Hit: {pct:.2f}% ≤ -{sl}%")
                api_result = call_exit_api(basket_id, False, True, reason=f"Margin SL: {sl}%")
                exit_triggered = api_result.get("success", False)
            else:
                print(f"✅ [BasketWide][Margin%] Within limits: {pct:.2f}% (TP: {tp}%, SL: -{sl}%)")
        else:
            print(f"⚠️ [BasketWide][Margin%] Total margin is {total_margin}, cannot calculate percentage")
            
    elif option_type == "time_based":
        now = datetime.now().strftime("%H:%M:%S")
        
        if tp and now >= tp:
            print(f"🎯 [BasketWide][Time] TP Time Hit: {now} ≥ {tp}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Time TP Exit: {tp}")
            exit_triggered = api_result.get("success", False)
        elif sl and now >= sl:
            print(f"🛑 [BasketWide][Time] SL Time Hit: {now} ≥ {sl}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Time SL Exit: {sl}")
            exit_triggered = api_result.get("success", False)
    else:
        print(f"⚠️ [BasketWide] Unknown option_type: {option_type}")
        return False
    
    if not exit_triggered:
        print(f"✅ Basket {basket_id}: No basket-wide condition hit")
    else:
        print(f"🚨 Basket {basket_id}: BASKET EXIT TRIGGERED")
        update_basket_exit_status_in_db(basket_id, cur, conn, f"Basket-wide exit: {option_type}")
    
    return exit_triggered

# FIXED: Also update the underlying risk function
def check_underlying_base_risk_fixed(basket_id: int, risk_cfg: dict, current_price: float, 
                              entry_price: float, cur, conn) -> bool:
    """
    FIXED: Underlying-based risk management with proper key mapping.
    """
    if not risk_cfg or current_price is None or entry_price is None:
        return False
    
    option_type = risk_cfg.get("option_type")
    if not option_type:
        print(f"❌ No option_type specified for underlying risk in basket {basket_id}")
        return False
    
    # FIXED: Use normalized key mapping
    tp, sl = get_normalized_risk_values(risk_cfg, option_type)
    
    print(f"🔍 Underlying Risk Analysis for Basket {basket_id}:")
    print(f"   Option Type: {option_type}")
    print(f"   TP: {tp}, SL: {sl}")
    print(f"   Current price: {current_price}, Entry price: {entry_price}")
    
    exit_triggered = False
    
    if option_type == "points_based":
        move = abs(current_price - entry_price)
        print(f"📊 [UnderlyingBase][Points] Move: {move:.2f} pts")
        
        if tp is not None and move >= tp:
            print(f"🎯 [UnderlyingBase][Points TP] {move:.2f} ≥ {tp}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Points-based TP: {tp} pts")
            exit_triggered = api_result.get("success", False)
        elif sl is not None and move >= sl:
            print(f"🛑 [UnderlyingBase][Points SL] {move:.2f} ≥ {sl}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Points-based SL: {sl} pts")
            exit_triggered = api_result.get("success", False)
        else:
            print(f"✅ [UnderlyingBase][Points] Within limits: {move:.2f} (TP: {tp}, SL: {sl})")
            
    elif option_type == "price_based":
        print(f"📊 [UnderlyingBase][Price] Current: ₹{current_price}")
        
        if tp is not None and current_price >= tp:
            print(f"🎯 [UnderlyingBase][Price TP] ₹{current_price} ≥ ₹{tp}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Price-based TP: ₹{tp}")
            exit_triggered = api_result.get("success", False)
        elif sl is not None and current_price <= sl:
            print(f"🛑 [UnderlyingBase][Price SL] ₹{current_price} ≤ ₹{sl}")
            api_result = call_exit_api(basket_id, False, True, reason=f"Price-based SL: ₹{sl}")
            exit_triggered = api_result.get("success", False)
        else:
            print(f"✅ [UnderlyingBase][Price] Within limits: ₹{current_price} (TP: ₹{tp}, SL: ₹{sl})")
    else:
        print(f"⚠️ [UnderlyingBase] Unknown option_type: {option_type}")
        return False
    
    if not exit_triggered:
        print(f"✅ Basket {basket_id}: No underlying-based condition hit")
    else:
        print(f"🚨 Basket {basket_id}: UNDERLYING EXIT TRIGGERED")
        update_basket_exit_status_in_db(basket_id, cur, conn, f"Underlying-based exit: {option_type}")
    
    return exit_triggered

# ====================================================================
# UNCHANGED: UTILITY FUNCTIONS
# ====================================================================
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







# ====================================================================
# COMPLETELY UPDATED: MAIN TRACKING FUNCTION WITH PROPER EXIT HANDLING
# ====================================================================
@celery.task(name="websocket_server.track_alert_task", bind=True)
def track_alert_task(self, alert_id: str):
    """
    COMPLETELY UPDATED: Now properly handles task termination when trades are exited.
    
    Key Changes:
    1. Tracks basket state locally (active_baskets)
    2. Periodically checks database for basket status
    3. Terminates when all baskets are exited
    4. Proper cleanup of resources
    5. Returns exit status from risk management functions
    6. [NEW] Resume mode: if alerts.status in (triggered/active/open), skip threshold re-trigger
    7. [CHANGED] underlying_token is int; keep underlying_price updated on each underlying tick
    8. [NEW] Guards to avoid running underlying-dependent rules before first underlying tick
    """
    conn = None
    pubsub = None
    
    try:
        # ====================================================================
        # STEP 1: SETUP AND INITIALIZATION
        # ====================================================================
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Load alert details (now also fetching status)
        cur.execute("""
            SELECT symbol, operator, threshold, valid_till, status, triggered_at
            FROM alerts
            WHERE id = ?
        """, (alert_id,))
        row = cur.fetchone()
        if not row:
            print(f"Alert '{alert_id}' not found.")
            return

        symbol, operator, threshold, valid_till, alert_status, triggered_at = row
        if str(alert_status).lower() == "waiting":
            if not is_before_valid_till(valid_till):
                print(f"Alert '{alert_id}' has expired at {valid_till}.")
                return

        print(f"🚀 START tracking alert={alert_id} symbol={symbol} op={operator} threshold={threshold}")
        
        # [NEW] Pre-set resume flags from alerts.status (finalization after baskets are loaded)
        resume = str(alert_status).lower() in {"triggered", "active", "open"}
        condition_met = False   # will finalize after loading baskets
        trade_active = False    # will finalize after loading baskets

        # Load baskets & their risk configs
        cur.execute("""
            SELECT id, risk_mode, margin_required
            FROM baskets
            WHERE alert_id = ?
        """, (alert_id,))
        
        baskets = []
        for basket_id, risk_mode, margin_required in cur.fetchall():
            baskets.append({
                "id": basket_id,
                "risk_mode": risk_mode,
                "margin_required": margin_required or 0.0
            })

        if not baskets:
            print("No baskets found for this alert; nothing to monitor.")
            return 

        # [NEW] Only arm trade in resume if at least one basket has a valid mode
        has_valid_mode = any(((b["risk_mode"] or "").strip().lower() in {"individual","basket","underlying"}) for b in baskets)
        if resume:
            condition_met = True
            trade_active = has_valid_mode
            print(f"♻️ RESUME mode for {symbol}: alerts.status={alert_status} (triggered_at={triggered_at}) → threshold check skipped; risk engines ON.")
            if not has_valid_mode:
                print("⚠️ No valid risk_mode → will not run risk management.")
        else:
            print(f"⏳ WAIT mode for {symbol}: alerts.status={alert_status} → normal threshold monitoring.")

        # ====================================================================
        # NEW: INITIALIZE BASKET STATE TRACKING
        # ====================================================================
        active_baskets = {b["id"]: True for b in baskets}
        last_activity_time = time.time()
        db_check_interval = 30  # Check database every 30 seconds
        last_db_check = time.time()
        max_inactive_time = 300  # 5 minutes without activity
        
        print(f"📋 Initialized tracking for {len(active_baskets)} baskets: {list(active_baskets.keys())}")
        
        # ====================================================================
        # STEP 2: TOKEN SUBSCRIPTION
        # ====================================================================
        tokens = set()
        try:
            # 3a) Underlying
            # [CHANGED] ensure underlying_token is int and also stored as int in tokens
            underlying_token = int(get_instrument_id(symbol))  # [CHANGED]
            tokens.add(underlying_token)                       # [CHANGED]

            # 3b) Each leg
            for b in baskets:
                bid = b["id"]
                cur.execute("""
                    SELECT instrument_type, symbol, strike, expiry
                    FROM legs
                    WHERE basket_id = ?
                """, (bid,))
                for instr_type, leg_sym, leg_strike, leg_expiry in cur.fetchall():
                    token_info = None
                    if instr_type in {'CE', 'PE'}:
                        leg_expiry = (leg_expiry or "").split(" ")[0]
                        token_info = get_instrument_token(leg_sym, leg_expiry, leg_strike, instr_type)
                    elif instr_type == 'FUT':
                        leg_expiry = (leg_expiry or "").split(" ")[0]
                        token_info = get_instrument_token(leg_sym, leg_expiry, 0, instr_type)
                    elif instr_type == 'EQ':
                        token_info = get_instrument_token(leg_sym, '', 0, 'EQ')

                    if token_info:
                        token, _ = token_info
                        tokens.add(int(token))
                    else:
                        print(f"[TokenError] Basket {bid} leg lookup failed: {leg_sym}/{instr_type}")

            tokens = list(tokens)
            # Register all tokens
            resp = requests.post(TICK_SERVICE_URL, json={"tokens": tokens}, timeout=30)
            resp.raise_for_status()
            print(f"✅ Subscribed tokens: {tokens}")

        except Exception as e:
            print(f"❌ Token registration error: {e}")
            return

        # ====================================================================
        # STEP 3: REDIS SUBSCRIPTION SETUP
        # ====================================================================
        pubsub = redis_client.pubsub()
        pubsub.subscribe("tick_channel")
        valid_modes = {"individual", "basket", "underlying"}

        # State variables (do NOT reset condition_met/trade_active here)
        current_prices = {}
        underlying_price = None
        underlying_threshold = threshold

        print(f"🔄 Starting main monitoring loop...")
        
        # ====================================================================
        # STEP 4: MAIN MONITORING LOOP WITH PROPER EXIT CONDITIONS
        # ====================================================================
        while True:
            current_time = time.time()
            
            # ================================================================
            # A) MARKET HOURS CHECK
            # ================================================================
            now = datetime.now()
            start = now.replace(hour=9, minute=0, second=0, microsecond=0)
            end = now.replace(hour=15, minute=30, second=0, microsecond=0)

            if now > end:
                print("📅 Market closed — stopping monitoring.")
                break

            # ================================================================
            # B) PERIODIC DATABASE STATE CHECK
            # ================================================================
            if current_time - last_db_check > db_check_interval:
                print("🔍 Checking database for basket status updates...")
                for basket_id in list(active_baskets.keys()):
                    if active_baskets[basket_id]:
                        if not check_basket_status_in_db(basket_id, cur):
                            active_baskets[basket_id] = False
                            print(f"📋 Basket {basket_id} marked inactive from database")
                
                last_db_check = current_time

            # ================================================================
            # C) CHECK IF ALL BASKETS ARE INACTIVE
            # ================================================================
            if not any(active_baskets.values()):
                print(f"🏁 ALL BASKETS INACTIVE for alert {alert_id} - TERMINATING MONITORING")
                break

            # ================================================================
            # D) INACTIVITY TIMEOUT CHECK
            # ================================================================
            if current_time - last_activity_time > max_inactive_time:
                print(f"⏰ No activity for {max_inactive_time}s - terminating monitoring")
                break

            # ================================================================
            # E) PROCESS REDIS TICK MESSAGES
            # ================================================================
            msg = pubsub.get_message()
            if not msg or msg.get("type") != "message":
                time.sleep(0.5)
                continue

            tick = json.loads(msg["data"])
            tok = tick.get("token")
            price = tick.get("price")
            if tok not in tokens:
                continue

            # Update price and activity tracking
            current_prices[tok] = price
            last_activity_time = current_time
            print(f"📊 TICK token={tok} @ price={price}")

            # [NEW] Keep underlying price updated for risk engines on every underlying tick
            if tok == underlying_token:  # [NEW]
                underlying_price = price  # [NEW]
    
            # ================================================================
            # F) ALERT TRIGGERING LOGIC (SKIPPED IN RESUME)
            # ================================================================
            if (not resume) and (not condition_met) and tok == underlying_token and compare(price, operator, threshold):
                print(f"🎯 ALERT TRIGGERED on {symbol} at {price}")
                
                trigger_url = f"http://192.168.4.221:9000/api/alerts/{alert_id}/trigger"
                payload = {
                    "trigger_price": price,
                    "trigger_time": datetime.now().isoformat()
                }
                try:
                    r = requests.post(trigger_url, json=payload, timeout=30)
                    r.raise_for_status()
                    print(f"✅ Trigger API succeeded")
                except Exception as e:
                    print(f"❌ Trigger API error: {e}")
                
                condition_met = True
                underlying_price = price
                trade_active = any((b["risk_mode"] or "").strip().lower() in valid_modes for b in baskets)
                
                if not trade_active:
                    print("⚠️ No valid risk_mode → skipping risk management.")

            # ================================================================
            # G) RISK MANAGEMENT WITH STATE TRACKING
            # ================================================================
            if condition_met and trade_active:
                for b in baskets:
                    basket_id = b["id"]
                    
                    # Skip inactive baskets
                    if not active_baskets.get(basket_id, False):
                        continue
                        
                    mode = (b["risk_mode"] or "").strip().lower()
                    total_margin = b['margin_required']
                    
                    print(f"🔧 Processing Basket {basket_id} with risk_mode: {mode}")
                    
                    # Load leg data
                    cur.execute("""
                        SELECT id AS leg_id, instrument_type, symbol, strike, expiry, 
                               premium as entry_premium, price AS entry_price, 
                               quantity, action, margin AS leg_margin 
                        FROM legs 
                        WHERE basket_id = ?
                    """, (basket_id,))
                    legs = cur.fetchall()

                    # Build leg_list and price map
                    leg_list = []
                    current_leg_prices = {}
                    for (leg_id, instr_type, sym, strike, expiry,
                         entry_prem, entry_price, quantity, action, leg_margin) in legs:
                        
                        # lookup live price token
                        if instr_type in ('CE','PE'):
                            expiry = (expiry or "").split(" ")[0]
                            tkn, _ = get_instrument_token(sym, expiry, strike, instr_type)
                        elif instr_type == 'FUT':
                            expiry = (expiry or "").split(" ")[0]
                            tkn, _ = get_instrument_token(sym, expiry, 0, instr_type)
                        else:  # EQ
                            tkn, _ = get_instrument_token(sym, '', 0, 'EQ')

                        live_price = current_prices.get(int(tkn)) if tkn else None
                        current_leg_prices[leg_id] = live_price

                        leg_list.append({
                            "leg_id": leg_id,
                            "instrument_type": instr_type,  # Added for risk management
                            "entry_premium": entry_prem if instr_type in ('CE','PE') else entry_price,
                            "entry_price": entry_price,  # Added for consistency
                            "quantity": quantity,
                            "action": action,
                            "margin": leg_margin
                        })
                    
                    # ========================================================
                    # INDIVIDUAL RISK MANAGEMENT
                    # ========================================================
                    if mode == "individual":
                        cur.execute("""
                            SELECT settings_json
                            FROM risk_settings
                            WHERE basket_id = ? AND risk_type = 'individual' AND is_active = 1
                        """, (basket_id,))
                        
                        risk_rows = cur.fetchall()
                        individual_risk_cfg = {}
                        
                        for r in risk_rows:
                            if r[0]:
                                try:
                                    risk_data = json.loads(r[0])
                                    if isinstance(risk_data, dict):
                                        individual_risk_cfg.update(risk_data)
                                except json.JSONDecodeError:
                                    print(f"⚠️ Invalid JSON in risk_settings for basket {basket_id}")

                        trade = {
                            "legs": leg_list,
                            "risk": {"individual_risk": individual_risk_cfg}
                        }
                        
                        # Call risk management and get exit status
                        exit_triggered = check_individual_leg_risk(
                            basket_id=basket_id,
                            trade=trade,
                            current_leg_prices=current_leg_prices,
                            cur=cur,
                            conn=conn
                        )
                        
                        # Update basket state
                        if exit_triggered:
                            active_baskets[basket_id] = False
                            print(f"🛑 Basket {basket_id} marked INACTIVE due to individual leg exit")
                    
                    # ========================================================
                    # BASKET-WIDE RISK MANAGEMENT
                    # ========================================================
                    elif mode == "basket":
                        # [NEW] Require first underlying tick; otherwise skip this loop
                        if underlying_price is None:  # [NEW]
                            continue                   # [NEW]

                        cur.execute("""
                            SELECT settings_json, option_type
                            FROM risk_settings
                            WHERE basket_id = ? AND risk_type = 'basket'
                        """, (basket_id,))
                        
                        row = cur.fetchone()
                        if row:
                            settings_json, option_type = row
                            basket_wide_cfg = json.loads(settings_json) if settings_json else {}
                            basket_wide_cfg['option_type'] = option_type
                        else:
                            basket_wide_cfg = {}

                        trade = {
                            "legs": leg_list,
                            "risk": {"basket": basket_wide_cfg}
                        }
                        
                        # Call risk management and get exit status
                        exit_triggered = check_basket_wide_risk_fixed(  # CHANGED
                            basket_id=basket_id,
                            trade=trade,
                            current_leg_prices=current_leg_prices,
                            current_underlying_price=underlying_price,
                            initial_underlying_price=underlying_threshold,
                            total_margin=total_margin,
                            cur=cur,
                            conn=conn
                        )
                        
                        # Update basket state
                        if exit_triggered:
                            active_baskets[basket_id] = False
                            print(f"🛑 Basket {basket_id} marked INACTIVE due to basket-wide exit")

                    # ========================================================
                    # UNDERLYING-BASED RISK MANAGEMENT
                    # ========================================================
                    elif mode == "underlying":
                        # [NEW] Require first underlying tick
                        if underlying_price is None:  # [NEW]
                            continue                   # [NEW]

                        cur.execute("""
                            SELECT settings_json, option_type
                            FROM risk_settings
                            WHERE basket_id = ? AND risk_type = 'underlying'
                        """, (basket_id,))
                        
                        row = cur.fetchone()
                        if row:
                            settings_json, option_type = row
                            underlying_cfg = json.loads(settings_json) if settings_json else {}
                            underlying_cfg['option_type'] = option_type
                        else:
                            underlying_cfg = {}

                        # Call risk management and get exit status
                        exit_triggered = check_underlying_base_risk_fixed(  # CHANGED
                            basket_id=basket_id,
                            risk_cfg=underlying_cfg,
                            current_price=underlying_price,
                            entry_price=underlying_threshold,
                            cur=cur,
                            conn=conn
                        )
                        
                        # Update basket state
                        if exit_triggered:
                            active_baskets[basket_id] = False
                            print(f"🛑 Basket {basket_id} marked INACTIVE due to underlying exit")

                    else:
                        print(f"⚠️ Basket {basket_id}: invalid risk_mode '{mode}'")
        
        print(f"🏁 Monitoring loop ended for alert {alert_id}")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in tracking task for alert {alert_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # [NEW] Clean up resources safely
        try:
            if pubsub:
                pubsub.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass

# ====================================================================
# ENTRY POINT (UNCHANGED)
# ====================================================================
if __name__ == "__main__":
    print("intialized sync task")
    # track_alert_task.delay("alert_1754971138_680")
    # track_alert_task.delay("alert_1754553031_544")
    # track_alert_task.delay("alert_1754553596_24")
    # track_alert_task.delay("alert_1754553835_504")
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Load alert details (now also fetching status)
    cur.execute("""
                SELECT DISTINCT id
                FROM alerts
                WHERE 
                    (
                        status = 'waiting' 
                        AND (valid_till IS NULL OR datetime(valid_till) >= datetime('now'))
                    )
                    OR status IN ('triggered','active');
                """)
    row = [i[0] for i in cur.fetchall()]
    print (row)
    # exit(0)
    for i in row:
        print(f"Starting task for alert {i}")
        track_alert_task.delay(i)
    