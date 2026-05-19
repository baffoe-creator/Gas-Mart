"""
SQLAlchemy ORM models and engine configuration for Gas Mart.
"""
import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker 

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "gas_mart.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
      DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 10  # seconds — prevents indefinite blocking
    },
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sales = relationship("Sale", back_populates="cashier")
    audit_logs = relationship("AuditLog", back_populates="user")
    price_list_modes = relationship("PriceListMode", back_populates="user")


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    demo_price = Column(Float, nullable=False)
    real_price = Column(Float, nullable=True)
    stock_qty = Column(Integer, default=0)
    reorder_threshold = Column(Integer, default=10)
    is_demo_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    sale_items = relationship("SaleItem", back_populates="product")
    inventory_alerts = relationship("InventoryAlert", back_populates="product")


class PriceListMode(Base):
    __tablename__ = "price_list_mode"
    
    id = Column(Integer, primary_key=True, index=True)
    mode = Column(String(20), nullable=False, default="demo")
    switched_at = Column(DateTime, default=datetime.utcnow)
    switched_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    user = relationship("User", back_populates="price_list_modes")


class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    cashier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="cart")
    subtotal = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total_ghs = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    cashier = relationship("User", back_populates="sales")
    sale_items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="sale", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price_ghs = Column(Float, nullable=False)
    line_total_ghs = Column(Float, nullable=False)
    
    sale = relationship("Sale", back_populates="sale_items")
    product = relationship("Product", back_populates="sale_items")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    payment_method = Column(String(50), nullable=False)
    mobile_money_network = Column(String(50), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    transaction_ref = Column(String(100), nullable=True)
    amount_ghs = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    paid_at = Column(DateTime, nullable=True)
    
    sale = relationship("Sale", back_populates="payments")


class Receipt(Base):
    __tablename__ = "receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    receipt_no = Column(String(50), unique=True, index=True, nullable=False)
    delivery_method = Column(String(50), nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow)
    
    sale = relationship("Sale", back_populates="receipts")


class InventoryAlert(Base):
    __tablename__ = "inventory_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty_at_alert = Column(Integer, nullable=False)
    is_resolved = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product", back_populates="inventory_alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details_json = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="audit_logs")


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Get a new database session."""
    return SessionLocal()