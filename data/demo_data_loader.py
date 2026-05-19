"""
Seeds demo data and first-run initialization.
"""
import os
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from data.database import User, Product, PriceListMode, Base, engine, SessionLocal
from logger import logger
import bcrypt

FIRST_RUN_FLAG = os.path.join(os.path.dirname(__file__), "..", "first_run.flag")
DEMO_PRICES_PATH = os.path.join(os.path.dirname(__file__), "demo_prices.json")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def load_demo_prices_json() -> list:
    """Load demo prices from JSON file."""
    if os.path.exists(DEMO_PRICES_PATH):
        with open(DEMO_PRICES_PATH, "r") as f:
            return json.load(f)
    return get_default_demo_prices()


def get_default_demo_prices() -> list:
    """Return default demo prices list."""
    return [
        {"barcode": "6001001", "name": "Voltic Water 500ml", "category": "Beverages", "demo_price": 2.00},
        {"barcode": "6001002", "name": "Club Energy Drink 250ml", "category": "Beverages", "demo_price": 8.50},
        {"barcode": "6001003", "name": "Pringles Original 40g", "category": "Snacks", "demo_price": 12.00},
        {"barcode": "6001004", "name": "Gardenia Bread Loaf", "category": "Bakery", "demo_price": 18.00},
        {"barcode": "6001005", "name": "MTN Airtime GHS 5", "category": "Airtime", "demo_price": 5.00},
        {"barcode": "6001006", "name": "MTN Airtime GHS 10", "category": "Airtime", "demo_price": 10.00},
        {"barcode": "6001007", "name": "Mentos Roll", "category": "Confectionery", "demo_price": 3.00},
        {"barcode": "6001008", "name": "Marlboro Red 20s", "category": "Tobacco", "demo_price": 35.00},
        {"barcode": "6001009", "name": "Dettol Sanitizer 50ml", "category": "Healthcare", "demo_price": 15.00},
        {"barcode": "6001010", "name": "Kleenex Tissues 200s", "category": "Household", "demo_price": 22.00},
        {"barcode": "6001011", "name": "Total Quartz 1L Engine Oil", "category": "Automotive", "demo_price": 85.00},
        {"barcode": "6001012", "name": "Glade Car Freshener", "category": "Automotive", "demo_price": 28.00},
        {"barcode": "6001013", "name": "Jacob's Creek Biscuits", "category": "Snacks", "demo_price": 9.50},
        {"barcode": "6001014", "name": "Wrigley's Doublemint Gum", "category": "Confectionery", "demo_price": 2.50},
        {"barcode": "6001015", "name": "Kit Kat Chocolate", "category": "Confectionery", "demo_price": 11.00},
        {"barcode": "6001016", "name": "Coca-Cola 500ml", "category": "Beverages", "demo_price": 6.00},
        {"barcode": "6001017", "name": "Minute Maid Orange Juice 300ml", "category": "Beverages", "demo_price": 7.50},
        {"barcode": "6001018", "name": "Fan Ice Vanilla 100ml", "category": "Dairy", "demo_price": 4.00},
        {"barcode": "6001019", "name": "Tuna Sandwich (ready-made)", "category": "Food", "demo_price": 25.00},
        {"barcode": "6001020", "name": "Nescafe Sachet 3-in-1", "category": "Beverages", "demo_price": 5.50},
    ]


def seed_database():
    """Seed database with demo data on first run."""
    session = SessionLocal()
    try:
        demo_prices = load_demo_prices_json()
        for item in demo_prices:
            existing = session.query(Product).filter_by(barcode=item["barcode"]).first()
            if not existing:
                product = Product(
                    barcode=item["barcode"],
                    name=item["name"],
                    category=item["category"],
                    demo_price=item["demo_price"],
                    real_price=None,
                    stock_qty=100,
                    reorder_threshold=10,
                    is_demo_active=True
                )
                session.add(product)
                logger.info(f"Seeded product: {item['name']}")
        
        existing_admin = session.query(User).filter_by(username="admin").first()
        if not existing_admin:
            admin_user = User(
                username="admin",
                password_hash=hash_password("Admin1234"),
                role="admin",
                is_active=True
            )
            session.add(admin_user)
            logger.info("Seeded admin user")
        
        session.commit()
        
        existing_mode = session.query(PriceListMode).first()
        if not existing_mode:
            admin = session.query(User).filter_by(username="admin").first()
            mode = PriceListMode(
                mode="demo",
                switched_by_user_id=admin.id if admin else None
            )
            session.add(mode)
            session.commit()
            logger.info("Seeded price_list_mode with demo mode")
        
        logger.info("Database seeding completed successfully")
        
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def run_first_time_setup():
    """Run first-time setup: create tables, seed data, create flag."""
    logger.info("Running first-time setup...")
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    seed_database()
    
    with open(FIRST_RUN_FLAG, "w") as f:
        f.write(str(datetime.now(timezone.utc)))
    logger.info("First run flag created")


def check_and_init():
    """Check if first run is needed and initialize if so."""
    if not os.path.exists(FIRST_RUN_FLAG):
        run_first_time_setup()
    else:
        logger.info("First run already completed. Skipping setup.")