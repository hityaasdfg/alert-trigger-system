import sqlite3
from datetime import datetime
DB_PATH = r"C:\Users\Alkalyme\Downloads\ato_project\ato_project\instance\ato_system.db"



alert_id = "alert_1754553031_544"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()


updates = {
    2: 663.65,
    3: 7844.50
}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

for leg_id, new_price in updates.items():
    query = "UPDATE legs SET pnl = ? WHERE id = ?"
    print("Executing query:", query, "with params:", (new_price, leg_id))
    cur.execute(query, (new_price, leg_id))


# cur.execute("UPDATE legs SET quantity = 0, price = 4209.85 WHERE basket_id = ( SELECT id FROM baskets WHERE id = 2 AND alert_id = 'alert_1754553596_24' );")
# Commit changes
conn.commit()
conn.close()

exit(0)

# 1️⃣ Get all baskets for this alert
cur.execute("SELECT id FROM baskets WHERE alert_id = ?", (alert_id,))
basket_ids = [row[0] for row in cur.fetchall()]
print(f"Basket IDs to delete: {basket_ids}")

# 2️⃣ Delete legs for these baskets
if basket_ids:
    leg_delete_query = f"DELETE FROM legs WHERE basket_id IN ({','.join(['?']*len(basket_ids))})"
    print("Executing query:", leg_delete_query, "with params:", basket_ids)
    cur.execute(leg_delete_query, basket_ids)

# 3️⃣ Delete risk_settings for these baskets
if basket_ids:
    risk_delete_query = f"DELETE FROM risk_settings WHERE basket_id IN ({','.join(['?']*len(basket_ids))})"
    print("Executing query:", risk_delete_query, "with params:", basket_ids)
    cur.execute(risk_delete_query, basket_ids)

# 4️⃣ Delete baskets
basket_delete_query = "DELETE FROM baskets WHERE alert_id = ?"
print("Executing query:", basket_delete_query, "with param:", alert_id)
cur.execute(basket_delete_query, (alert_id,))

# 5️⃣ Delete the alert itself
alert_delete_query = "DELETE FROM alerts WHERE id = ?"
print("Executing query:", alert_delete_query, "with param:", alert_id)
cur.execute(alert_delete_query, (alert_id,))

# Commit changes
conn.commit()
conn.close()

print(f"✅ Alert {alert_id} and all related baskets, legs, and risk settings deleted.")

exit(0)




exited_at      = '2025-08-26 15:15:00'
basket_id      = 2
exit_price     = 4544.00
exit_quantity  = 2
leg_id         = 2   

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# # ✅ Update legs
# cur.execute("""
#     UPDATE legs
#     SET exit_price = ?,
#         exit_quantity = ?,
#         exit_price_type = ?,
#         exit_timestamp = ?,
#         status = 'exited',
#         exited_at = ?
#     WHERE basket_id = ?
#       AND (id = ? OR ? IS NULL)
# """, (exit_price, exit_quantity, "market", exited_at, exited_at, basket_id, leg_id, leg_id))

# # ✅ Update baskets
# cur.execute("""
#     UPDATE baskets
#     SET status = 'exited',
#         exited_at = ?,
#         exit_reason = 'Exited by script'
#     WHERE id = ?
# """, (exited_at, basket_id))

# # ✅ Update alerts
# cur.execute("""
#     UPDATE alerts
#     SET status = 'completed',
#         completed_at = ?
#     WHERE id = ?
# """, (exited_at, "alert_1754553596_24"))

# conn.commit()
# conn.close()

# print(f"✅ Basket {basket_id}, Leg {leg_id}, and Alert alert_1754553596_24 marked as completed at {exited_at}")

# ✅ Update valid_till for all alerts
today = datetime.now().strftime("%Y-%m-%d")
fixed_time = f"{today} 15:20:00"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
    UPDATE alerts
    SET valid_till = ?
""", (fixed_time,))

conn.commit()
conn.close()

print(f"✅ All alerts valid_till updated to {fixed_time}")

exit(0)






    

# """
# Test script for email notifications using alert_1754553031_544
# """
# import sqlite3
# import datetime
# from dataclasses import dataclass
# from typing import List, Optional
# import sys

# # Database configuration
# DB_PATH = r"C:\Users\Alkalyme\Downloads\ato_project\ato_project\instance\ato_system.db"

# def execute_sql_query(query, params=None, fetch=False, multi=False):
#     """
#     Execute SQL query. Supports both single and multiple statements.
#     """
#     conn = sqlite3.connect(DB_PATH)
#     try:
#         cursor = conn.cursor()

#         if multi:
#             cursor.executescript(query)
#         else:
#             if params:
#                 cursor.execute(query, params)
#             else:
#                 cursor.execute(query)

#         conn.commit()

#         if fetch:
#             return cursor.fetchall()
#         return cursor.rowcount

#     except Exception as e:
#         print(f"⚠️ SQL Error: {e}")
#         return None
#     finally:
#         conn.close()

# # Data classes to structure the fetched data
# @dataclass
# class Leg:
#     action: str
#     symbol: str
#     quantity: int
#     strike: str = ""
#     margin: float = 0
#     option_type: str = ""
#     risk_selected: bool = False
#     risk_type: str = ""
#     sl: str = ""
#     tp: str = ""
#     status: str = "pending"
#     premium: Optional[float] = None
#     price: Optional[float] = None
#     pnl: Optional[float] = None

# @dataclass
# class Basket:
#     label: str
#     strategy: str
#     legs: List[Leg]
#     status: str = "pending"
#     exit_reason: Optional[str] = None
#     exited_at: Optional[datetime.datetime] = None

# @dataclass
# class Alert:
#     symbol: str
#     operator: str
#     threshold: float
#     valid_till: datetime.datetime
#     triggered_at: Optional[datetime.datetime] = None
#     total_margin_required: float = 0
#     baskets: List[Basket] = None

# def fetch_alert_data(alert_id: str):
#     """
#     Fetch alert data from database
#     """
#     print(f"🔍 Fetching data for alert: {alert_id}")
    
#     # Fetch main alert data
#     alert_query = """
#     SELECT symbol, condition_operator, threshold_value, valid_till, 
#            triggered_at, total_margin_required, status
#     FROM alerts 
#     WHERE alert_id = ?
#     """
    
#     alert_data = execute_sql_query(alert_query, (alert_id,), fetch=True)
    
#     if not alert_data:
#         print(f"❌ Alert {alert_id} not found!")
#         return None
    
#     alert_row = alert_data[0]
    
#     # Parse dates
#     valid_till = datetime.datetime.strptime(alert_row[3], '%Y-%m-%d %H:%M:%S') if alert_row[3] else datetime.datetime.now()
#     triggered_at = datetime.datetime.strptime(alert_row[4], '%Y-%m-%d %H:%M:%S') if alert_row[4] else None
    
#     # Create alert object
#     alert = Alert(
#         symbol=alert_row[0],
#         operator=alert_row[1],
#         threshold=float(alert_row[2]),
#         valid_till=valid_till,
#         triggered_at=triggered_at,
#         total_margin_required=float(alert_row[5] or 0)
#     )
    
#     print(f"✅ Alert found: {alert.symbol} {alert.operator} {alert.threshold}")
#     return alert

# def fetch_baskets_data(alert_id: str):
#     """
#     Fetch baskets and legs data for the alert
#     """
#     print(f"🔍 Fetching baskets for alert: {alert_id}")
    
#     # Fetch baskets
#     baskets_query = """
#     SELECT basket_id, label, strategy, status, exit_reason, exited_at
#     FROM baskets 
#     WHERE alert_id = ?
#     ORDER BY basket_id
#     """
    
#     baskets_data = execute_sql_query(baskets_query, (alert_id,), fetch=True)
    
#     if not baskets_data:
#         print(f"❌ No baskets found for alert {alert_id}")
#         return []
    
#     baskets = []
#     baskets_dict_data = []  # For the create email function
    
#     for basket_row in baskets_data:
#         basket_id = basket_row[0]
        
#         # Fetch legs for this basket
#         legs_query = """
#         SELECT action, symbol, quantity, strike_price, margin_required,
#                option_type, risk_selected, risk_type, stop_loss, take_profit,
#                status, premium, execution_price, pnl
#         FROM legs 
#         WHERE basket_id = ?
#         ORDER BY leg_id
#         """
        
#         legs_data = execute_sql_query(legs_query, (basket_id,), fetch=True)
        
#         legs = []
#         legs_dict = []  # For dictionary format
        
#         for leg_row in legs_data:
#             leg = Leg(
#                 action=leg_row[0],
#                 symbol=leg_row[1],
#                 quantity=int(leg_row[2]) if leg_row[2] else 0,
#                 strike=str(leg_row[3]) if leg_row[3] else "",
#                 margin=float(leg_row[4]) if leg_row[4] else 0,
#                 option_type=leg_row[5] if leg_row[5] else "",
#                 risk_selected=bool(leg_row[6]) if leg_row[6] else False,
#                 risk_type=leg_row[7] if leg_row[7] else "",
#                 sl=str(leg_row[8]) if leg_row[8] else "",
#                 tp=str(leg_row[9]) if leg_row[9] else "",
#                 status=leg_row[10] if leg_row[10] else "pending",
#                 premium=float(leg_row[11]) if leg_row[11] else None,
#                 price=float(leg_row[12]) if leg_row[12] else None,
#                 pnl=float(leg_row[13]) if leg_row[13] else None
#             )
#             legs.append(leg)
            
#             # Dictionary format for create email
#             legs_dict.append({
#                 'action': leg.action,
#                 'symbol': leg.symbol,
#                 'quantity': leg.quantity,
#                 'strike': leg.strike,
#                 'margin': leg.margin,
#                 'option_type': leg.option_type,
#                 'risk_selected': leg.risk_selected,
#                 'risk_type': leg.risk_type,
#                 'sl': leg.sl,
#                 'tp': leg.tp
#             })
        
#         # Parse exit date
#         exited_at = None
#         if basket_row[5]:
#             try:
#                 exited_at = datetime.datetime.strptime(basket_row[5], '%Y-%m-%d %H:%M:%S')
#             except:
#                 pass
        
#         basket = Basket(
#             label=basket_row[1] if basket_row[1] else f"Basket {len(baskets) + 1}",
#             strategy=basket_row[2] if basket_row[2] else "custom",
#             legs=legs,
#             status=basket_row[3] if basket_row[3] else "pending",
#             exit_reason=basket_row[4],
#             exited_at=exited_at
#         )
#         baskets.append(basket)
        
#         # Dictionary format for create email
#         baskets_dict_data.append({
#             'label': basket.label,
#             'strategy': basket.strategy,
#             'legs': legs_dict
#         })
    
#     print(f"✅ Found {len(baskets)} baskets with total {sum(len(b.legs) for b in baskets)} legs")
#     return baskets, baskets_dict_data

# def test_alert_created_email(alert, baskets_dict_data):
#     """
#     Test the alert creation email
#     """
#     print("\n" + "="*50)
#     print("📧 Testing Alert Created Email")
#     print("="*50)
    
#     try:
#         from send_email import generate_and_send_email
#         success = generate_and_send_email(alert, baskets_dict_data)
#         print(f"✅ Alert Created Email: {'SUCCESS' if success else 'FAILED'}")
#         return success
#     except Exception as e:
#         print(f"❌ Alert Created Email FAILED: {e}")
#         return False

# def test_execution_email(alert):
#     """
#     Test the alert execution email
#     """
#     print("\n" + "="*50)
#     print("📧 Testing Alert Execution Email")
#     print("="*50)
    
#     try:
#         from send_email import generate_and_send_execution_email
#         success = generate_and_send_execution_email(alert)
#         print(f"✅ Execution Email: {'SUCCESS' if success else 'FAILED'}")
#         return success
#     except Exception as e:
#         print(f"❌ Execution Email FAILED: {e}")
#         return False

# def test_exit_email(alert, basket, exit_type="Stop Loss"):
#     """
#     Test the basket exit email
#     """
#     print("\n" + "="*50)
#     print(f"📧 Testing Exit Email ({exit_type})")
#     print("="*50)
    
#     try:
#         from send_email import generate_and_send_exit_email
#         success = generate_and_send_exit_email(alert, basket, exit_type)
#         print(f"✅ Exit Email: {'SUCCESS' if success else 'FAILED'}")
#         return success
#     except Exception as e:
#         print(f"❌ Exit Email FAILED: {e}")
#         return False

# def test_order_success_email():
#     """
#     Test the order success email with sample data
#     """
#     print("\n" + "="*50)
#     print("📧 Testing Order Success Email")
#     print("="*50)
    
#     try:
#         from send_email import send_order_success_email
#         success = send_order_success_email(
#             tradingsymbol="NIFTY25207PE",
#             qty=50,
#             price=125.50,
#             action="B",
#             order_type="LIMIT",
#             order_id="240807000123456",
#             filled_qty=50,
#             executed_price=125.25
#         )
#         print(f"✅ Order Success Email: {'SUCCESS' if success else 'FAILED'}")
#         return success
#     except Exception as e:
#         print(f"❌ Order Success Email FAILED: {e}")
#         return False

# def main():
#     """
#     Main test function
#     """
#     alert_id = "alert_1754553031_544"
    
#     print("🚀 Starting Email Notification Tests")
#     print(f"📋 Alert ID: {alert_id}")
#     print("="*60)
    
#     # Fetch data from database
#     alert = fetch_alert_data(alert_id)
#     if not alert:
#         print("❌ Cannot proceed without alert data")
#         return
    
#     baskets, baskets_dict_data = fetch_baskets_data(alert_id)
#     if not baskets:
#         print("❌ Cannot proceed without basket data")
#         return
    
#     # Attach baskets to alert
#     alert.baskets = baskets
    
#     # Test results
#     results = {}
    
#     # Test 1: Alert Created Email
#     results['alert_created'] = test_alert_created_email(alert, baskets_dict_data)
    
#     # Test 2: Alert Execution Email
#     results['execution'] = test_execution_email(alert)
    
#     # Test 3: Exit Email (test with first basket)
#     if baskets:
#         results['exit'] = test_exit_email(alert, baskets[0], "Stop Loss")
    
#     # Test 4: Order Success Email
#     results['order_success'] = test_order_success_email()
    
#     # Summary
#     print("\n" + "="*60)
#     print("📊 TEST SUMMARY")
#     print("="*60)
    
#     for test_name, success in results.items():
#         status = "✅ PASS" if success else "❌ FAIL"
#         print(f"{test_name.replace('_', ' ').title()}: {status}")
    
#     total_tests = len(results)
#     passed_tests = sum(results.values())
    
#     print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
#     if passed_tests == total_tests:
#         print("🎉 All email tests PASSED!")
#     else:
#         print("⚠️ Some email tests FAILED. Check the logs above.")

# if __name__ == "__main__":
#     main()




# # query = "SELECT settings_json FROM risk_settings WHERE basket_id = ? AND risk_type = 'individual' AND is_active = 1"
# # result = execute_sql_query(query, params=('8,',), fetch=True)
# # print(result)

# # created_at = db.Column(db.DateTime, default=lambda: datetime.now()) of 2025-08-04 9:00:00 AM
# query = """
#     UPDATE alerts 
#     SET created_at = '2025-08-06 08:41:10'  
#     WHERE id = 'alert_1754553835_504';

# """
# # UPDATE baskets 
# # SET label = 'PGHL CUP AND HANDLE BREAKOUT' 
# # WHERE alert_id = 'alert_1754553031_544';

# # execute_sql_query(query, multi=True)
# # print("✅ All table data deleted.")
# # exit(0)


# # delete_all_query = """
# #     DELETE FROM risk_settings;
# #     DELETE FROM legs;
# #     DELETE FROM baskets;
# #     DELETE FROM alerts;
# # """

# # execute_sql_query(delete_all_query, multi=True)
# # print("✅ All table data deleted.")
# # exit(0)




# # query = """
# # UPDATE risk_settings
# # SET settings_json = json_set(
# #     settings_json,
# #     '$.sl', 24550
# # )
# # WHERE id = 8; 
# # """



# # rows_affected = execute_sql_query(query, multi=True)
# # print(f"Rows updated (multi-statement): {rows_affected}")
# # exit(0)

# # # query = "DELETE FROM alerts WHERE id = ?"
# # # rows_deleted = execute_sql_query(query, params=('alert_xyz',))
# # # print(f"Rows deleted: {rows_deleted}")

# # import os
# # import sys
# # import json
# # from datetime import datetime, timedelta

# # import requests

# # # ── CONFIG ────────────────────────────────────────────────────────────────
# # BASE_URL = os.getenv("ALERT_API_BASE", "http://192.168.4.221:9000")
# # USER_KEY = os.getenv("USER_KEY", "6107a84358676f862be226daae343418")


# # def create_covered_call_alert():
# #     """NIFTY Covered-Call with Basket-Wide PnL-% Risk (–0.5% SL / +1% TP)"""
# #     return {
# #         "symbol": "NIFTY",
# #         "operator": ">=",
# #         "threshold": 18000,
# #         "valid_till": "2025-08-06T23:59:59",
# #         "session_user": USER_KEY,
# #         "total_margin_required": 18200,
# #         "baskets": [
# #             {
# #                 "label": "NIFTY Covered Call – Basket % Risk",
# #                 "strategy": "covered_call",
# #                 "risk_mode": "basket",
# #                 "margin_required": 18200,
# #                 "legs": [
# #                     {
# #                         "action": "B",
# #                         "instrument_type": "FUT",
# #                         "symbol": "NIFTY",
# #                         "expiry": "2025-08-28",
# #                         "strike": None,               # ← explicit strike=0 for FUT
# #                         "quantity": 75,
# #                         "price": 24500,
# #                         "premium_type": "market"
# #                     },
# #                     {
# #                         "action": "S",
# #                         "instrument_type": "CE",
# #                         "symbol": "NIFTY",
# #                         "expiry": "2025-08-14",
# #                         "strike": 24500,
# #                         "quantity": 75,
# #                         "price": 200,
# #                         "premium_type": "market"
# #                     }
# #                 ],
# #                 "risk_management": {
# #                     "settings": {
# #                         "basket": {
# #                             "option_type": "pnl_margin_percentage",
# #                             "tp": 1.0,
# #                             "sl": 0.5
# #                         }
# #                     }
# #                 }
# #             }
# #         ]
# #     }



# # def post_alert(payload):
# #     url = f"{BASE_URL}/api/alerts"
# #     try:
# #         resp = requests.post(url, json=payload, timeout=10)
# #     except requests.RequestException as e:
# #         print(f"❌ Failed to connect to {url}:", e, file=sys.stderr)
# #         return False

# #     print(f"→ POST {url}  status={resp.status_code}")
# #     try:
# #         print(json.dumps(resp.json(), indent=2))
# #     except ValueError:
# #         print("Response was not valid JSON:")
# #         print(resp.text)

# #     return resp.ok

# # def main():
# #     payload = create_covered_call_alert()
# #     if not post_alert(payload):
# #         sys.exit(1)

# # if __name__ == "__main__":
# #     main()



