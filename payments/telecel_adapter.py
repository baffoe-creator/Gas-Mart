"""
Telecel Cash adapter (mock offline).
"""
import time
import random
import string
from payments.base import MoMoAdapter, PaymentError
from logger import logger


class TelecelAdapter(MoMoAdapter):
    """Telecel Cash adapter with offline mock."""
    
    def __init__(self):
        self.transactions = {}
    
    def initiate(self, phone: str, amount: float) -> dict:
        """Initiate Telecel payment."""
        try:
            if not self._validate_phone(phone):
                raise PaymentError(f"Invalid Telecel phone number: {phone}")
            
            transaction_ref = f"TEL-{self._generate_ref()}"
            self.transactions[transaction_ref] = {
                "phone": phone,
                "amount": amount,
                "status": "PENDING",
                "initiated_at": time.time()
            }
            
            logger.info(f"Telecel payment initiated: ref={transaction_ref}, phone={phone}, amount={amount}")
            return {"ref": transaction_ref, "status": "PENDING"}
            
        except Exception as e:
            logger.error(f"Telecel initiate error: {e}")
            raise (f"Telecel payment initiation failed: {e}")
    
    def poll_status(self, transaction_ref: str) -> str:
        """Poll Telecel payment status."""
        try:
            if transaction_ref not in self.transactions:
                raise PaymentError(f"Transaction {transaction_ref} not found")
            
            time.sleep(2)
            
            if random.random() < 0.9:
                self.transactions[transaction_ref]["status"] = "SUCCESS"
                logger.info(f"Telecel payment succeeded: {transaction_ref}")
                return "SUCCESS"
            else:
                self.transactions[transaction_ref]["status"] = "FAILED"
                logger.warning(f"Telecel payment failed: {transaction_ref}")
                return "FAILED"
            
        except Exception as e:
            logger.error(f"Telecel poll_status error: {e}")
            raise PaymentError(f"Telecel status poll failed: {e}")
    
    @staticmethod
    def _validate_phone(phone: str) -> bool:
        """Validate Ghana Telecel phone number format."""
        valid_prefixes = ["020", "050"]
        if len(phone) != 10 or not phone.isdigit():
            return False
        return phone[:3] in valid_prefixes
    
    @staticmethod
    def _generate_ref() -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))