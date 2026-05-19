"""
AirtelTigo Money adapter (mock offline).
"""
import time
import random
import string
from payments.base import MoMoAdapter, PaymentError
from logger import logger


class AirtelTigoAdapter(MoMoAdapter):
    """AirtelTigo Money adapter with offline mock."""
    
    def __init__(self):
        self.transactions = {}
    
    def initiate(self, phone: str, amount: float) -> dict:
        """Initiate AirtelTigo payment."""
        try:
            if not self._validate_phone(phone):
                raise PaymentError(f"Invalid AirtelTigo phone number: {phone}")
            
            transaction_ref = f"ATG-{self._generate_ref()}"
            self.transactions[transaction_ref] = {
                "phone": phone,
                "amount": amount,
                "status": "PENDING",
                "initiated_at": time.time()
            }
            
            logger.info(f"AirtelTigo payment initiated: ref={transaction_ref}, phone={phone}, amount={amount}")
            return {"ref": transaction_ref, "status": "PENDING"}
            
        except Exception as e:
            logger.error(f"AirtelTigo initiate error: {e}")
            raise PaymentError(f"AirtelTigo payment initiation failed: {e}")
    
    def poll_status(self, transaction_ref: str) -> str:
        """Poll AirtelTigo payment status."""
        try:
            if transaction_ref not in self.transactions:
                raise PaymentError(f"Transaction {transaction_ref} not found")
            
            time.sleep(2)
            
            if random.random() < 0.9:
                self.transactions[transaction_ref]["status"] = "SUCCESS"
                logger.info(f"AirtelTigo payment succeeded: {transaction_ref}")
                return "SUCCESS"
            else:
                self.transactions[transaction_ref]["status"] = "FAILED"
                logger.warning(f"AirtelTigo payment failed: {transaction_ref}")
                return "FAILED"
            
        except Exception as e:
            logger.error(f"AirtelTigo poll_status error: {e}")
            raise PaymentError(f"AirtelTigo status poll failed: {e}")
    
    @staticmethod
    def _validate_phone(phone: str) -> bool:
        """Validate Ghana AirtelTigo phone number format."""
        valid_prefixes = ["027", "057", "026", "056"]
        if len(phone) != 10 or not phone.isdigit():
            return False
        return phone[:3] in valid_prefixes
    
    @staticmethod
    def _generate_ref() -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))