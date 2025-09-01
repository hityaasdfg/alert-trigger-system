# constants.py

# File paths and configuration constants

# Path to the Zerodha access token file
# ACCESS_TOKEN_PATH = r'\\Velocity\c\Users\kunal\Downloads\LIVE_TICK_HIGH_LOW_FLASK\LIVE_TICK_HIGH_LOW_FLASK\zerodha_access_token.txt'

# # Path to the instruments CSV file
# INSTRUMENTS_CSV_PATH = r'C:\Users\Hitesh Divekar\Downloads\project\project\instruments.csv'

# # Path to the SQLite database
# SQLITE_DB_PATH = r'sqlite:///C:\Users\Hitesh Divekar\Downloads\project\ato_project\instance\ato_system.db'

# # Path to the Flask template folder
# TEMPLATE_FOLDER_PATH = r'C:\Users\Hitesh Divekar\Downloads\project\ato_project\static\templates'

# Add more constants as needed


# constants.py

import os

# ─── Files & Paths (Custom Machine Paths) ────────────────────────────────
ACCESS_TOKEN_PATH      = r'\\Velocity\c\Users\kunal\Downloads\LIVE_TICK_HIGH_LOW_FLASK\LIVE_TICK_HIGH_LOW_FLASK\zerodha_access_token.txt'
INSTRUMENTS_CSV_PATH   = r'C:\Users\Alkalyme\Downloads\ato_project\ato_project\instruments.csv'
SQLITE_DB_PATH         = r'sqlite:///C:\Users\Alkalyme\Downloads\ato_project\ato_project\instance\ato_system.db'
TEMPLATE_FOLDER_PATH   = r'C:\Users\Alkalyme\Downloads\ato_project\ato_project\static\templates'

# ─── Kite API Keys ───────────────────────────────────────────────────────
KITE_API_KEY    = 'zuuxkho8imp70m8c'         # Replace with your key
KITE_API_SECRET = open(ACCESS_TOKEN_PATH)     # Optional for login

# ─── Redis Config ────────────────────────────────────────────────────────
REDIS_URL = 'redis://localhost:6379/0'

# ─── Timezone ────────────────────────────────────────────────────────────
TIMEZONE = 'Asia/Kolkata'
