"""
Tests for authentication and authorization.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data.database import Base, User
from logic.auth import AuthService, AuthenticationError, AuthorizationError


@pytest.fixture
def session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def sample_user(session):
    """Create a sample user for testing."""
    user = User(
        username="testuser",
        password_hash=AuthService.hash_password("TestPass123"),
        role="cashier",
        is_active=True
    )
    session.add(user)
    session.commit()
    return user


def test_hash_password():
    """Test password hashing."""
    password = "MyPassword123"
    hashed = AuthService.hash_password(password)
    assert hashed != password
    assert AuthService.verify_password(password, hashed)


def test_login_success(session, sample_user):
    """Test successful login."""
    user = AuthService.login("testuser", "TestPass123", session)
    assert user.username == "testuser"
    assert user.is_active


def test_login_user_not_found(session):
    """Test login with non-existent user."""
    with pytest.raises(AuthenticationError):
        AuthService.login("nonexistent", "password", session)


def test_login_wrong_password(session, sample_user):
    """Test login with wrong password."""
    with pytest.raises(AuthenticationError):
        AuthService.login("testuser", "WrongPassword", session)


def test_login_inactive_user(session, sample_user):
    """Test login with inactive user."""
    sample_user.is_active = False
    session.commit()
    
    with pytest.raises(AuthenticationError):
        AuthService.login("testuser", "TestPass123", session)


def test_check_role_admin(session):
    """Test that admin has all permissions."""
    admin = User(
        username="admin",
        password_hash=AuthService.hash_password("admin"),
        role="admin",
        is_active=True
    )
    session.add(admin)
    session.commit()
    
    # Should not raise
    AuthService.check_role(admin, "cashier")
    AuthService.check_role(admin, "manager")


def test_check_role_mismatch(session, sample_user):
    """Test role mismatch."""
    with pytest.raises(AuthorizationError):
        AuthService.check_role(sample_user, "admin")


def test_check_roles_multiple(session, sample_user):
    """Test checking multiple allowed roles."""
    # Should not raise
    AuthService.check_roles(sample_user, ["cashier", "manager"])


def test_check_roles_mismatch(session, sample_user):
    """Test roles mismatch."""
    with pytest.raises(AuthorizationError):
        AuthService.check_roles(sample_user, ["admin", "manager"])


def test_create_user(session, sample_user):
    """Test creating a new user."""
    new_user = AuthService.create_user(
        "newuser",
        "NewPass123",
        "manager",
        sample_user.id,
        session
    )
    assert new_user.username == "newuser"
    assert new_user.role == "manager"
    
    # Verify password is hashed
    assert AuthService.verify_password("NewPass123", new_user.password_hash)


def test_create_duplicate_user(session, sample_user):
    """Test creating duplicate user."""
    with pytest.raises(ValueError):
        AuthService.create_user(
            "testuser",
            "NewPass123",
            "cashier",
            sample_user.id,
            session
        )


def test_create_invalid_role(session, sample_user):
    """Test creating user with invalid role."""
    with pytest.raises(ValueError):
        AuthService.create_user(
            "newuser",
            "NewPass123",
            "invalid_role",
            sample_user.id,
            session
        )


def test_deactivate_user(session, sample_user):
    """Test deactivating a user."""
    admin = User(
        username="admin",
        password_hash=AuthService.hash_password("admin"),
        role="admin",
        is_active=True
    )
    session.add(admin)
    session.commit()
    
    AuthService.deactivate_user(sample_user.id, admin.id, session)
    
    user = session.query(User).filter_by(id=sample_user.id).first()
    assert not user.is_active