"""
Configuration constants for Gas Mart.
"""
import os

# Application settings
APP_NAME = "TOTAL MART - ACCRA"
APP_VERSION = "1.0.0"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

# Database
DB_NAME = "gas_mart.db"

# Payment settings
PAYMENT_TIMEOUT_SECONDS = 60
PAYMENT_POLL_INTERVAL = 1

# Receipt settings
RECEIPT_PRINT_WIDTH = 80  # ESC/POS width in characters

# Price modes
PRICE_MODE_DEMO = "demo"
PRICE_MODE_REAL = "real"

# User roles
ROLE_ADMIN = "admin"
ROLE_CASHIER = "cashier"
ROLE_MANAGER = "manager"

# Payment methods
PAYMENT_CASH = "cash"
PAYMENT_CARD = "card"
PAYMENT_MTN = "mtn"
PAYMENT_TELECEL = "telecel"
PAYMENT_AIRTELTIGO = "airteltigo"

# Ghana phone prefixes for mobile money
GHANA_PHONE_PREFIXES = {
    "mtn": ["024", "054", "055", "059"],
    "telecel": ["020", "050"],
    "airteltigo": ["027", "057", "026", "056"]
}

# Discount limits
MIN_DISCOUNT_PERCENT = 0.0
MAX_DISCOUNT_PERCENT = 20.0

# ==================== MTN COLLECTION API SETTINGS ====================
# Base URL for MTN Collection API
MTN_API_BASE_URL = os.getenv("MTN_API_BASE_URL", "https://sandbox.momodeveloper.mtn.com/collection")

# MTN API Subscription Key (from MTN Developer Portal)
MTN_API_KEY = os.getenv("MTN_API_KEY", "")

# MTN API User ID (from MTN Developer Portal)
MTN_API_USER = os.getenv("MTN_API_USER", "")

# MTN API User Password (from MTN Developer Portal)
MTN_API_PASSWORD = os.getenv("MTN_API_PASSWORD", "")

# Target Environment (sandbox or production)
MTN_TARGET_ENVIRONMENT = os.getenv("MTN_TARGET_ENVIRONMENT", "sandbox")

# Optional Callback URL for payment status updates
MTN_CALLBACK_URL = os.getenv("MTN_CALLBACK_URL", "")

# MTN API Request timeout in seconds
MTN_REQUEST_TIMEOUT = int(os.getenv("MTN_REQUEST_TIMEOUT", "30"))

# Enable MTN Collection API (set to False to use mock adapter for testing)
MTN_COLLECTION_ENABLED = os.getenv("MTN_COLLECTION_ENABLED", "True").lower() == "true"

# MTN Currency code (GHS for Ghana Cedi)
MTN_CURRENCY = "GHS"

# MTN API version prefix
MTN_API_VERSION_PREFIX = "v1_0"
