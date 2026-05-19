"""
Tests for payment processing.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data.database import Base, Product, PriceListMode, User, Sale, Payment
from logic.pos import CartService
from payments.payments import PaymentService
from payments.mtn_adapter import MTNAdapter
from payments.telecel_adapter import TelecelAdapter
from payments.airteltigo_adapter import AirtelTigoAdapter
from payments.base import PaymentError
from logic.auth import AuthService


@pytest.fixture
def session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def setup_data(session):
    """Setup test data."""
    # Create products
    product = Product(
        barcode="6001001",
        name="Water 500ml",
        category="Beverages",
        demo_price=2.00,
        stock_qty=100
    )
    session.add(product)
    
    # Create price mode
    mode = PriceListMode(mode="demo")
    session.add(mode)
    
    # Create user
    user = User(
        username="cashier",
        password_hash=AuthService.hash_password("pass"),
        role="cashier",
        is_active=True
    )
    session.add(user)
    session.commit()
    
    return product, mode, user


def test_process_cash_payment_success(session, setup_data):
    """Test successful cash payment."""
    product, mode, cashier = setup_data
    
    # Create sale
    cart = CartService(session)
    cart.add_item("6001001", 5)
    sale_id = cart.commit_sale(cashier.id)
    
    # Process payment
    payment_service = PaymentService(session)
    result = payment_service.process_cash_payment(sale_id, 15.00, cashier.id)
    
    assert result["status"] == "completed"
    assert result["change"] == 10.00
    
    # Verify payment record
    payment = session.query(Payment).filter_by(sale_id=sale_id).first()
    assert payment.payment_method == "cash"
    assert payment.status == "completed"


def test_process_cash_payment_insufficient(session, setup_data):
    """Test cash payment with insufficient amount."""
    product, mode, cashier = setup_data
    
    cart = CartService(session)
    cart.add_item("6001001", 5)  # 10.00 GHS
    sale_id = cart.commit_sale(cashier.id)
    
    payment_service = PaymentService(session)
    with pytest.raises(PaymentError):
        payment_service.process_cash_payment(sale_id, 5.00, cashier.id)


def test_process_card_payment(session, setup_data):
    """Test card payment."""
    product, mode, cashier = setup_data
    
    cart = CartService(session)
    cart.add_item("6001001", 3)
    sale_id = cart.commit_sale(cashier.id)
    
    payment_service = PaymentService(session)
    result = payment_service.process_card_payment(sale_id, cashier.id)
    
    assert result["status"] == "completed"
    
    payment = session.query(Payment).filter_by(sale_id=sale_id).first()
    assert payment.payment_method == "card"


def test_mtn_adapter_initiate(session):
    """Test MTN adapter initiation."""
    adapter = MTNAdapter()
    result = adapter.initiate("0245551234", 50.00)
    
    assert result["status"] == "PENDING"
    assert result["ref"].startswith("MTN-")


def test_mtn_adapter_invalid_phone(session):
    """Test MTN adapter with invalid phone."""
    adapter = MTNAdapter()
    with pytest.raises(PaymentError):
        adapter.initiate("1234567890", 50.00)


def test_telecel_adapter_initiate(session):
    """Test Telecel adapter initiation."""
    adapter = TelecelAdapter()
    result = adapter.initiate("0201234567", 50.00)
    
    assert result["status"] == "PENDING"
    assert result["ref"].startswith("TEL-")


def test_airteltigo_adapter_initiate(session):
    """Test AirtelTigo adapter initiation."""
    adapter = AirtelTigoAdapter()
    result = adapter.initiate("0271234567", 50.00)
    
    assert result["status"] == "PENDING"
    assert result["ref"].startswith("ATG-")


def test_mtn_adapter_poll_status(session):
    """Test MTN adapter poll status."""
    adapter = MTNAdapter()
    result = adapter.initiate("0245551234", 50.00)
    transaction_ref = result["ref"]
    
    status = adapter.poll_status(transaction_ref)
    assert status in ["SUCCESS", "FAILED"]