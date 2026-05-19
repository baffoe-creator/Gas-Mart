"""
Authentication and authorization logic.
"""
import bcrypt
from sqlalchemy.orm import Session
from data.database import User
from data.audit_logger import AuditLogger
from logger import logger
from datetime import datetime
import json

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""
    pass


class AuthService:
    """Service for user authentication and RBAC."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            # Ensure password_hash is bytes
            if isinstance(password_hash, str):
                password_hash = password_hash.encode("utf-8")
            
            # Ensure password is bytes
            password_bytes = password.encode("utf-8")
            
            # Verify
            result = bcrypt.checkpw(password_bytes, password_hash)
            logger.debug(f"Password verification: {result}")
            return result
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    @staticmethod
    def login(username: str, password: str, session: Session) -> User:
        """
        Authenticate a user and return their record.
        Raises AuthenticationError if credentials are invalid or user is inactive.
        """
        try:
            user = session.query(User).filter_by(username=username).first()
            
            if not user:
                AuditLogger.log_action(session, None, "login_failed", 
                                   json.dumps({"username": username, "reason": "user_not_found"}))
                raise AuthenticationError(f"User '{username}' not found")
            
            if not user.is_active:
                AuditLogger.log_action(session, user.id, "login_failed",
                                   json.dumps({"username": username, "reason": "user_inactive"}))
                raise AuthenticationError(f"User '{username}' is inactive")
            
            if not AuthService.verify_password(password, user.password_hash):
                AuditLogger.log_action(session, user.id, "login_failed",
                                   json.dumps({"username": username, "reason": "wrong_password"}))
                raise AuthenticationError("Incorrect password")
            
            AuditLogger.log_action(session, user.id, "login_success", 
                               json.dumps({"username": username}))
            logger.info(f"User '{username}' logged in successfully")
            return user
            
        except AuthenticationError as e:
            raise
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise AuthenticationError("Login failed due to an error")
    
    @staticmethod
    def logout(user_id: int, session: Session):
        """Log a user logout."""
        try:
            AuditLogger.log_action(session, user_id, "logout", json.dumps({}))
            logger.info(f"User {user_id} logged out")
        except Exception as e:
            logger.error(f"Logout error: {e}")
    
    @staticmethod
    def check_role(user: User, required_role: str):
        """Check if user has required role. Raises AuthorizationError if not."""
        if user.role == "admin":
            return
        if user.role != required_role:
            raise AuthorizationError(f"User role '{user.role}' does not match required role '{required_role}'")
    
    @staticmethod
    def check_roles(user: User, required_roles: list):
        """Check if user has one of the required roles."""
        if user.role == "admin":
            return
        if user.role not in required_roles:
            raise AuthorizationError(f"User role '{user.role}' not in allowed roles {required_roles}")
    
    @staticmethod
    def create_user(username: str, password: str, role: str, created_by_user_id: int, session: Session) -> User:
        """Create a new user. Only admins can create users."""
        try:
            existing = session.query(User).filter_by(username=username).first()
            if existing:
                raise ValueError(f"User '{username}' already exists")
            
            if role not in ["admin", "cashier", "manager"]:
                raise ValueError(f"Invalid role: {role}")
            
            new_user = User(
                username=username,
                password_hash=AuthService.hash_password(password),
                role=role,
                is_active=True
            )
            session.add(new_user)
            session.flush()
            
            AuditLogger.log_action(session, created_by_user_id, "user_created",
                               json.dumps({"username": username, "role": role}))
            session.commit()
            logger.info(f"User '{username}' created with role '{role}'")
            return new_user
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating user: {e}")
            raise
    
    @staticmethod
    def deactivate_user(user_id: int, deactivated_by_user_id: int, session: Session):
        """Deactivate a user."""
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User with id {user_id} not found")
            
            user.is_active = False
            session.commit()
            
            AuditLogger.log_action(session, deactivated_by_user_id, "user_deactivated",
                               json.dumps({"user_id": user_id, "username": user.username}))
            logger.info(f"User '{user.username}' deactivated")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error deactivating user: {e}")
            raise