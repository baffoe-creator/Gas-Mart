"""
Abstract base class for Mobile Money adapters.
"""
from abc import ABC, abstractmethod


class PaymentError(Exception):
    """Raised when a payment operation fails."""
    pass


class MoMoAdapter(ABC):
    """Abstract base class for Mobile Money payment adapters."""
    
    @abstractmethod
    def initiate(self, phone: str, amount: float) -> dict:
        """
        Initiate a payment request.
        Returns: {"ref": "transaction_ref", "status": "PENDING"}
        """
        pass
    
    @abstractmethod
    def poll_status(self, transaction_ref: str) -> str:
        """
        Poll the status of a payment.
        Returns: "PENDING", "SUCCESS", or "FAILED"
        """
        pass
