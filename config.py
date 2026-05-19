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