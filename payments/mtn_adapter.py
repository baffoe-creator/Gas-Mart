"""
MTN MoMo adapter (mock offline).
"""
import time
import random
import string
from payments.base import MoMoAdapter, PaymentError
from logger import logger


class MTNAdapter(MoMoAdapter):
    """MTN Mobile Money adapter with offline mock."""
    
    def __init__(self):
        self.transactions = {}  # In-memory transaction store
    
    def initiate(self, phone: str, amount: float) -> dict:
        """Initiate MTN payment. Returns immediately with PENDING status."""
        try:
            if not self._validate_phone(phone):
                raise PaymentError(f"Invalid MTN phone number: {phone}")
            
            transaction_ref = f"MTN-{self._generate_ref()}"
            self.transactions[transaction_ref] = {
                "phone": phone,
                "amount": amount,
                "status": "PENDING",
                "initiated_at": time.time()
            }
            
            logger.info(f"MTN payment initiated: ref={transaction_ref}, phone={phone}, amount={amount}")
            return {"ref": transaction_ref, "status": "PENDING"}
            
        except Exception as e:
            logger.error(f"MTN initiate error: {e}")
            raise PaymentError(f"MTN payment initiation failed: {e}")
    
    def poll_status(self, transaction_ref: str) -> str:
        """Poll MTN payment status. Returns SUCCESS after 2 second delay."""
        try:
            if transaction_ref not in self.transactions:
                raise PaymentError(f"Transaction {transaction_ref} not found")
            
            # Simulate network delay
            time.sleep(2)
            
            # Mock: randomly succeed or fail (90% success rate)
            if random.random() < 0.9:
                self.transactions[transaction_ref]["status"] = "SUCCESS"
                logger.info(f"MTN payment succeeded: {transaction_ref}")
                return "SUCCESS"
            else:
                self.transactions[transaction_ref]["status"] = "FAILED"
                logger.warning(f"MTN payment failed: {transaction_ref}")
                return "FAILED"
            
        except Exception as e:
            logger.error(f"MTN poll_status error: {e}")
            raise PaymentError(f"MTN status poll failed: {e}")
    
    @staticmethod
    def _validate_phone(phone: str) -> bool:
        """Validate Ghana MTN phone number format."""
        valid_prefixes = ["024", "054", "055", "059"]
        if len(phone) != 10 or not phone.isdigit():
            return False
        return phone[:3] in valid_prefixes
    
    @staticmethod
    def _generate_ref() -> str:
        """Generate a random transaction reference."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))