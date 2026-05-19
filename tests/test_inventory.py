"""
Tests for inventory management.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data.database import Base, Product, InventoryAlert
from logic.inventory import InventoryService


@pytest.fixture
def session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def sample_product(session):
    """Create sample product."""
    product = Product(
        barcode="6001001",
        name="Water 500ml",
        category="Beverages",
        demo_price=2.00,
        stock_qty=100,
        reorder_threshold=10
    )
    session.add(product)
    session.commit()
    return product


def test_decrement_stock(session, sample_product):
    """Test decrementing stock."""
    InventoryService.decrement_stock(sample_product.id, 10, session)
    
    product = session.query(Product).filter_by(id=sample_product.id).first()
    assert product.stock_qty == 90


def test_decrement_stock_insufficient(session, sample_product):
    """Test decrementing with insufficient stock."""
    with pytest.raises(ValueError):
        InventoryService.decrement_stock(sample_product.id, 150, session)


def test_increment_stock(session, sample_product):
    """Test incrementing stock."""
    InventoryService.increment_stock(sample_product.id, 50, session)
    
    product = session.query(Product).filter_by(id=sample_product.id).first()
    assert product.stock_qty == 150


def test_check_low_stock_alert_created(session, sample_product):
    """Test low stock alert creation."""
    InventoryService.decrement_stock(sample_product.id, 95, session)
    
    alerts = session.query(InventoryAlert).filter_by(
        product_id=sample_product.id,
        is_resolved=False
    ).all()
    
    assert len(alerts) == 1


def test_check_low_stock_no_duplicate_alert(session, sample_product):
    """Test no duplicate alerts for same product."""
    InventoryService.decrement_stock(sample_product.id, 95, session)
    InventoryService.decrement_stock(sample_product.id, 3, session)
    
    alerts = session.query(InventoryAlert).filter_by(
        product_id=sample_product.id,
        is_resolved=False
    ).all()
    
    assert len(alerts) == 1


def test_resolve_alert(session, sample_product):
    """Test resolving alert."""
    InventoryService.decrement_stock(sample_product.id, 95, session)
    
    alert = session.query(InventoryAlert).filter_by(product_id=sample_product.id).first()
    InventoryService.resolve_alert(alert.id, session)
    
    alert = session.query(InventoryAlert).filter_by(id=alert.id).first()
    assert alert.is_resolved


def test_update_product_price(session, sample_product):
    """Test updating product real price."""
    InventoryService.update_product_price(sample_product.id, 2.50, session)
    
    product = session.query(Product).filter_by(id=sample_product.id).first()
    assert product.real_price == 2.50


def test_add_product(session):
    """Test adding new product."""
    product = InventoryService.add_product(
        "6001099",
        "Test Product",
        "Test",
        99.99,
        50,
        5,
        session
    )
    
    assert product.barcode == "6001099"
    assert product.name == "Test Product"


def test_add_duplicate_product(session, sample_product):
    """Test adding duplicate product."""
    with pytest.raises(ValueError):
        InventoryService.add_product(
            "6001001",
            "Duplicate",
            "Test",
            1.00,
            10,
            5,
            session
        )


def test_get_low_stock_products(session):
    """Test getting low stock products."""
    p1 = Product(
        barcode="6001001",
        name="Water",
        category="Beverages",
        demo_price=2.00,
        stock_qty=5,
        reorder_threshold=10
    )
    p2 = Product(
        barcode="6001002",
        name="Cola",
        category="Beverages",
        demo_price=6.00,
        stock_qty=50,
        reorder_threshold=10
    )
    session.add(p1)
    session.add(p2)
    session.commit()
    
    low_stock = InventoryService.get_low_stock_products(session)
    assert len(low_stock) == 1
    assert low_stock[0].barcode == "6001001"