"""THIS SCRIPT EMAILS SWING TRADE SCANNER'S SIGNAL"""

import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from decimal import Decimal
import sys, os


EMAIL_USER='reports@alkalyme.com'
SMTP_SERVER='smtp.gmail.com'
SMTP_PORT=587
DEFAULT_EMAIL_TO='hitesh.divekar@alkalyme.com'
DEFAULT_EMAIL_CC='hitesh.divekar@alkalyme.com'
EMAIL_PASSWORD = 'snwhdlzbzwuczlsf'

def send_email(subject: str, body: str, to: str = None, cc: str = None):
    """
    Improved send_email function with better security and error handling
    """
    try:
        # Use environment variables for security
        email_user = EMAIL_USER
        email_password =EMAIL_PASSWORD
        smtp_server = SMTP_SERVER
        smtp_port = SMTP_PORT
        
        if not email_password:
            print("[EMAIL ERROR] Email password not configured in environment variables")
            return False
            
        # Default recipients if none provided
        default_to = DEFAULT_EMAIL_TO
        default_cc = DEFAULT_EMAIL_CC
        
        to = to or default_to
        cc = cc or default_cc
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)

        message = MIMEMultipart()
        message['From'] = email_user
        
        # Parse recipients
        recipients = []
        if to:
            recipients.extend([email.strip() for email in to.split(',')])
        if cc:
            recipients.extend([email.strip() for email in cc.split(',')])

        evaluation_date = datetime.datetime.today().strftime('%d-%m-%Y')
        
        message['Date'] = formatdate(localtime=True)
        message['Subject'] = subject + f" - {evaluation_date}"
        message['To'] = to
        if cc:
            message['Cc'] = cc

        message.attach(MIMEText(body, 'plain'))

        server.sendmail(message['From'], recipients, message.as_string())
        server.close()
        
        print(f"[EMAIL] Successfully sent: {subject}")
        return True
        
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email '{subject}': {e}")
        return False

def generate_and_send_email(alert, baskets_data):
    """
    Send notification when a new alert is created - unchanged logic
    """
    lines = []
    lines.append(f"✅ Alert Created Successfully")
    lines.append(f"Symbol: {alert.symbol}")
    lines.append(f"Condition: {alert.symbol} {alert.operator} {alert.threshold}")
    lines.append(f"Valid Till: {alert.valid_till.strftime('%d-%m-%Y %H:%M')}")
    lines.append(f"Total Margin: ₹{int(alert.total_margin_required):,}\n")

    for i, basket in enumerate(baskets_data, 1):
        label = basket.get('label', f'Basket {i}')
        strategy = basket.get('strategy', 'custom')
        legs = basket.get('legs', [])
        margin = sum(leg.get('margin', 0) for leg in legs)

        lines.append(f"{i}. {label} | Strategy: {strategy}")

        for j, leg in enumerate(legs, 1):
            action = leg.get('action', '').upper()
            symbol = leg.get('symbol', '')
            qty = leg.get('quantity', '')
            strike = leg.get('strike', '')
            margin = leg.get('margin', 0)
            option_type = leg.get('option_type', '').upper()
            risk_selected = leg.get('risk_selected', False) or leg.get('is_risk_selected', False)
            risk_type = leg.get('risk_type', '')
            sl = leg.get('sl', '')
            tp = leg.get('tp', '')

            lines.append(f"   - Leg {j}: {action} {qty} of {symbol} {option_type} {f'Strike: {strike}' if strike else ''}")
            lines.append(f"       ↪ Margin: ₹{int(margin):,} | Risk: {'Yes' if risk_selected else 'No'} | Type: {risk_type} | SL: {sl} | TP: {tp}")
        lines.append("")

    lines.append("Regards,\nAlkalyme Alert System")
    body = '\n'.join(lines)
    return send_email(subject="New ATO Alert Created", body=body)

def generate_and_send_execution_email(alert):
    """
    FIXED: Send notification when alert is triggered - now checks actual leg status
    """
    lines = [
        f"📣 Alert Triggered: {alert.symbol}",
        f"Condition: {alert.symbol} {alert.operator} {alert.threshold}",
        f"Triggered At: {alert.triggered_at.strftime('%d-%m-%Y %H:%M:%S')}\n"
    ]

    # Track execution status
    total_legs = 0
    successful_legs = 0
    failed_legs = 0
    pending_legs = 0

    for i, basket in enumerate(alert.baskets, 1):
        lines.append(f"{i}. Basket: {basket.label or f'Basket {i}'} | Status: {basket.status}")
        
        for leg in basket.legs:
            total_legs += 1
            
            # Determine status and count
            if hasattr(leg, 'status'):
                if leg.status in ['executed', 'complete', 'filled']:
                    successful_legs += 1
                    status_icon = "✅"
                elif leg.status in ['failed', 'rejected', 'cancelled']:
                    failed_legs += 1
                    status_icon = "❌"
                else:
                    pending_legs += 1
                    status_icon = "⏳"
            else:
                # If no status attribute, assume pending
                pending_legs += 1
                status_icon = "⏳"
                leg.status = "pending"
            
            # Format price information
            price_info = ""
            if hasattr(leg, 'premium') and leg.premium:
                price_info = f"@ ₹{leg.premium:.2f}"
            elif hasattr(leg, 'price') and leg.price:
                price_info = f"@ ₹{leg.price:.2f}"
                
            lines.append(
                f"   - {status_icon} {leg.action.upper()} {leg.quantity} of {leg.symbol} {price_info} ({leg.status})"
            )
        lines.append("")

    # FIXED: Add accurate execution summary based on actual results
    if total_legs == 0:
        lines.append("⚠️ No legs found in alert.")
    elif failed_legs == 0 and pending_legs == 0 and successful_legs == total_legs:
        lines.append("✅ All legs executed successfully.")
    elif failed_legs > 0:
        lines.append(f"⚠️ Execution Summary: {successful_legs}/{total_legs} legs successful, {failed_legs} failed.")
        if pending_legs > 0:
            lines.append(f"   {pending_legs} legs still pending.")
    elif pending_legs > 0:
        lines.append(f"⏳ Execution in progress: {successful_legs}/{total_legs} legs completed, {pending_legs} pending.")
    else:
        lines.append(f"📊 Execution Summary: {successful_legs} successful, {failed_legs} failed, {pending_legs} pending.")
        
    lines.append("\nRegards,\nAlkalyme Alert System")
    body = '\n'.join(lines)

    return send_email(subject="🔔 ATO Alert Triggered", body=body)

def generate_and_send_exit_email(alert, basket, exit_type):
    """
    Send notification when basket is exited - with improved error handling
    """
    try:
        lines = []
        lines.append(f"🔴 Basket Exit Notification")
        lines.append(f"Symbol: {alert.symbol}")
        lines.append(f"Condition: {alert.symbol} {alert.operator} {alert.threshold}")
        lines.append(f"Exit Type: {exit_type}")
        lines.append(f"Exit Reason: {basket.exit_reason or 'N/A'}")
        
        # Safe date formatting
        if hasattr(basket, 'exited_at') and basket.exited_at:
            exit_time = basket.exited_at.strftime('%d-%m-%Y %H:%M')
        else:
            exit_time = 'N/A'
        lines.append(f"Exited At: {exit_time}")
        lines.append("")

        lines.append(f"📦 Basket: {basket.label or 'Unnamed'} | Strategy: {basket.strategy or 'custom'}")
        
        total_pnl = 0
        for leg in basket.legs:
            status_icon = "✅" if getattr(leg, 'status', '') == "exited" else "⏳"
            
            # Safe PnL calculation
            if hasattr(leg, 'pnl') and leg.pnl is not None:
                pnl_text = f"PnL: ₹{int(leg.pnl):,}"
                total_pnl += leg.pnl
            else:
                pnl_text = "PnL: N/A"
                
            lines.append(f" - {status_icon} {leg.action.upper()} {leg.quantity} of {leg.symbol} | {pnl_text}")
        
        # Add total PnL if available
        if total_pnl != 0:
            lines.append(f"\n💰 Total Basket PnL: ₹{int(total_pnl):,}")
        
        lines.append("")
        lines.append("Regards,\nAlkalyme Alert System")
        body = '\n'.join(lines)

        return send_email(subject=f"{exit_type.title()} Executed - {alert.symbol}", body=body)
        
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to generate exit email: {e}")
        return False

def send_order_success_email(tradingsymbol, qty, price, action, order_type,
                             order_id, filled_qty, executed_price):
    """
    Send notification when order is successfully placed - improved formatting
    """
    subject = "✅ Order Successfully Placed"
    
    # Improved action formatting
    action_text = 'Buy' if action.upper() in ['B', 'BUY'] else 'Sell'
    
    body_lines = [
        "📋 Order Details:",
        f"Trading Symbol: {tradingsymbol}",
        f"Quantity: {qty:,}" if isinstance(qty, (int, float)) else f"Quantity: {qty}",
        f"Price: ₹{price:,.2f}" if isinstance(price, (int, float)) else f"Price: {price}",
        f"Action: {action_text}",
        f"Order Type: {order_type.upper()}",
        "",
        "✅ Execution Details:",
        f"Order ID: {order_id}",
        f"Filled Quantity: {filled_qty:,}" if isinstance(filled_qty, (int, float)) else f"Filled Quantity: {filled_qty}",
        f"Executed Price: ₹{executed_price:,.2f}" if isinstance(executed_price, (int, float)) else f"Executed Price: {executed_price}",
        "",
        "Regards,",
        "Alkalyme Alert System"
    ]
    body = "\n".join(body_lines)
    
    try:
        success = send_email(subject=subject, body=body)
        if success:
            print("[EMAIL] Order success email sent.")
        return success
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send order success email: {e}")
        return False
    
    
    
def send_gtt_created_email(tradingsymbol, qty, trigger_price, action, order_type, gtt_id):
    subject = "⏱️ GTT Created (Pre‑open fallback)"
    action_text = 'Buy' if action.upper() in ['B', 'BUY'] else 'Sell'
    body_lines = [
        "📋 GTT Details:",
        f"Trading Symbol: {tradingsymbol}",
        f"Quantity: {qty:,}" if isinstance(qty, (int, float)) else f"Quantity: {qty}",
        f"Trigger @ Price: ₹{trigger_price:,.2f}" if isinstance(trigger_price, (int, float)) else f"Trigger @ Price: {trigger_price}",
        f"Action: {action_text}",
        f"Order Type (post-trigger): {order_type.upper()}",
        "",
        "✅ Created:",
        f"GTT ID: {gtt_id}",
        "",
        "Note: This was placed because REGULAR orders are blocked during the pre‑open gap.",
        "",
        "Regards,",
        "Alkalyme Alert System"
    ]
    try:
        ok = send_email(subject=subject, body="\n".join(body_lines))
        if ok: print("[EMAIL] GTT created email sent.")
        return ok
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send GTT email: {e}")
        return False