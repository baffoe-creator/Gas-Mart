"""
Audit logging utilities.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from data.database import AuditLog as AuditLogModel
from logger import logger
import json


class AuditLogger:
    """Static methods for audit logging."""
    
    @staticmethod
    def log_action(session: Session, user_id: int = None, action: str = "", 
                   details_json: str = None, ip_address: str = None):
        """Log an action to the audit_logs table."""
        try:
            audit_entry = AuditLogModel(
                user_id=user_id,
                action=action,
                details_json=details_json or "{}",
                ip_address=ip_address,
                timestamp=datetime.utcnow()
            )
            session.add(audit_entry)
            session.commit()
            logger.debug(f"Audit log created: action={action}, user_id={user_id}")
        except Exception as e:
            logger.error(f"Error logging audit action: {e}")
            session.rollback()