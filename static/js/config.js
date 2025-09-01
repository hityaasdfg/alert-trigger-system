const API_BASE_URL = 'http://192.168.4.221:9000/api';

const STRATEGIES = {
    "long_call": [
        ["B", "CE"]
    ],
    "short_call": [
        ["S", "CE"]
    ],
    "long_put": [
        ["B", "PE"]
    ],
    "short_put": [
        ["S", "PE"]
    ],
    "bullish_credit_spread": [
        ["S", "PE"],
        ["B", "PE"]
    ],
    "bearish_credit_spread": [
        ["S", "CE"],
        ["B", "CE"]
    ],
    "bullish_debit_spread": [
        ["B", "CE"],
        ["S", "CE"]
    ],
    "bearish_debit_spread": [
        ["B", "PE"],
        ["S", "PE"]
    ],
    "covered_call": [
        ["B", "FUT"],
        ["S", "CE"]
    ],
    "covered_put": [
        ["S", "FUT"],
        ["B", "PE"]
    ],
    "iron_condor": [
        ["S", "CE"],
        ["B", "CE"],
        ["S", "PE"],
        ["B", "PE"]
    ],
    "short_strangle": [
        ["S", "CE"],
        ["S", "PE"]
    ],
    "long_collar": [
        ["B", "FUT"],
        ["S", "PE"]
    ],
    "long_future": [
        ["B", "FUT"]
    ],
    "short_future": [
        ["S", "FUT"]
    ]
};

const RISK_MANAGEMENT_OPTIONS = {
    "basket_wide": {
        "net_pnl_tp_sl": "Net PnL Take Profit / Stop Loss",
        "pnl_margin_percentage": "PnL % on Total Margin",
        "time_based": "Time"
    },
    "underlying_based": {
        "price_based": "Underlying Price Based Exit",
        "points_based": "Points Movement Based"
    },
    "drawdown": {
        "amount_based": "Drawdown Amount Based",
        "percentage_based": "Drawdown Percentage Based"
    },
    "trailing": {
        "points_trailing": "Points Based Trailing SL",
        "percentage_trailing": "Percentage Based Trailing SL"
    },
    "advanced": {
        "risk_reward_ratio": "Risk:Reward Ratio Exit",
        "time_based": "Time Based Exit",
        "margin_utilization": "Margin Utilization Exit",
        "greeks_iv_based": "Greeks & IV Based Exit",
        "combined_conditions": "Combined Condition Exit"
    }
};

const MARGIN_CONFIG = {
    'CE': {
        base: 150,
        multiplier: 1.2
    },
    'PE': {
        base: 150,
        multiplier: 1.2
    },
    'FUT': {
        base: 50000,
        multiplier: 0.1
    },
    'EQ': {
        base: 0,
        multiplier: 0.2
    }
};

