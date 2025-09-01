from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.types import JSON
from datetime import datetime
import json
from constants import SQLITE_DB_PATH
import os
db = SQLAlchemy(session_options={'autoflush': False})

# ========================================
# DATABASE MODELS
# ========================================

class Alert(db.Model):
    """Alert model for triggering automated trades"""
    __tablename__ = 'alerts'
    
    id = db.Column(db.String(50), primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)  # NIFTY, BANKNIFTY, etc.
    operator = db.Column(db.String(5), nullable=False)  # >, <, >=, <=, ==
    threshold = db.Column(db.Float, nullable=False)
    valid_till = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, triggered, completed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    triggered_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    total_margin_required = db.Column(db.Float, default=0.0)
    session_user = db.Column(db.String(100))

    # Relationships
    baskets = db.relationship('Basket', backref='alert', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        # Generate ID if not provided
        if 'id' not in kwargs:
            kwargs['id'] = f"alert_{int(datetime.now().timestamp())}_{id(self) % 1000}"
        super().__init__(**kwargs)
    
    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'operator': self.operator,
            'threshold': self.threshold,
            'valid_till': self.valid_till.isoformat() if self.valid_till else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'total_margin_required': self.total_margin_required,
            'baskets': [basket.to_dict() for basket in self.baskets],
            'session_user': self.session_user  
        }

class Basket(db.Model):
    """Basket model for grouping trading legs"""
    __tablename__ = 'baskets'
    
    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.String(50), db.ForeignKey('alerts.id'), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    strategy = db.Column(db.String(50), nullable=True)  # long_call, iron_condor, etc.
    risk_mode = db.Column(db.String(20), default='individual')  # individual, basket, underlying, etc.
    margin_required = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active')  # active, exited
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    exited_at = db.Column(db.DateTime, nullable=True)
    exit_reason = db.Column(db.String(200), nullable=True)
    live_scanner_id  = db.Column(db.Integer, nullable=True)
    # Relationships
    legs = db.relationship('Leg', backref='basket', lazy=True, cascade='all, delete-orphan')
    risk_settings = db.relationship('RiskSetting', backref='basket', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'label': self.label,
            'strategy': self.strategy,
            'risk_mode': self.risk_mode,
            'margin_required': self.margin_required,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'exited_at': self.exited_at.isoformat() if self.exited_at else None,
            'exit_reason': self.exit_reason,
            'legs': [leg.to_dict() for leg in self.legs],
            'risk_settings': [rs.to_dict() for rs in self.risk_settings],
            'live_scanner_id': self.live_scanner_id,
        }

class Leg(db.Model):
    """Leg model for individual trading positions"""
    __tablename__ = 'legs'
    
    id = db.Column(db.Integer, primary_key=True)
    basket_id = db.Column(db.Integer, db.ForeignKey('baskets.id'), nullable=False)
    action = db.Column(db.String(5), nullable=False)  # B (Buy), S (Sell)
    instrument_type = db.Column(db.String(10), nullable=False)  # CE, PE, FUT, EQ
    symbol = db.Column(db.String(20), nullable=False)
    strike = db.Column(db.Float, nullable=True)  # For options
    expiry = db.Column(db.DateTime, nullable=True)  # For options/futures
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=True)  # For equity
    premium = db.Column(db.Float, nullable=True)  # For options
    premium_type = db.Column(db.String(20), nullable=True)  # best_bid, best_ask, market_price, etc.
    margin = db.Column(db.Float, default=0.0)
    sl = db.Column(db.Float, nullable=True)  # Stop Loss
    tp = db.Column(db.Float, nullable=True)  # Take Profit
    exit_price = db.Column(db.Float, nullable=True)
    exit_quantity = db.Column(db.Integer, nullable=True)  
    exit_price_type = db.Column(db.String(20), nullable=True)  # market, limit, best_bid, best_ask
    exit_timestamp = db.Column(db.DateTime, nullable=True)
    
    # Optional: for tracking multiple partial exits
    partial_exits = db.Column(MutableList.as_mutable(JSON), default=list)
    pnl = db.Column(db.Float, nullable=True)  # Add this line     
    
    status = db.Column(db.String(20), default='pending')  # pending, executed, exited
    created_at = db.Column(db.DateTime, default=datetime.now())
    executed_at = db.Column(db.DateTime, nullable=True)
    exited_at = db.Column(db.DateTime, nullable=True)
    trade_instrument_token    = db.Column(db.BigInteger, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'basket_id': self.basket_id,
            'action': self.action,
            'instrument_type': self.instrument_type,
            'symbol': self.symbol,
            'strike': self.strike,
            'expiry': self.expiry.isoformat() if self.expiry else None,
            'quantity': self.quantity,
            'price': self.price,
            'premium': self.premium,
            'premium_type': self.premium_type,
            'margin': self.margin,
            'sl': self.sl,
            'tp': self.tp,
            'exit_price': self.exit_price,
            'exit_quantity': self.exit_quantity,
            'exit_price_type': self.exit_price_type,
            'exit_timestamp': self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            'partial_exits': self.partial_exits,
            'pnl': self.pnl,  # ✅ newly added field
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'exited_at': self.exited_at.isoformat() if self.exited_at else None,
            "trade_instrument_token": self.trade_instrument_token,  # ← add here
        }

class RiskSetting(db.Model):
    """Risk management settings for baskets"""
    __tablename__ = 'risk_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    basket_id = db.Column(db.Integer, db.ForeignKey('baskets.id'), nullable=False)
    risk_type = db.Column(db.String(20), nullable=False)  # basket, underlying, drawdown, trailing, advanced
    option_type = db.Column(db.String(50), nullable=False)  # net_pnl_tp_sl, price_based, etc.
    settings_json = db.Column(db.Text, nullable=True)  # JSON string of settings
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    
    def get_settings(self):
        """Parse JSON settings"""
        if self.settings_json:
            try:
                return json.loads(self.settings_json)
            except:
                return {}
        return {}
    
    def set_settings(self, settings_dict):
        """Set settings as JSON"""
        self.settings_json = json.dumps(settings_dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'basket_id': self.basket_id,
            'risk_type': self.risk_type,
            'option_type': self.option_type,
            'settings': self.get_settings(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }