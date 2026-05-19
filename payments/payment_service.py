"""
Main payment orchestration service.
"""
import time
from datetime import datetime
from sqlalchemy.orm import Session
from data.database import Payment, Sale, get_session
from logic.pos import CartService, InvalidStateError
from logic.inventory import InventoryService
from payments.base import PaymentError, MoMoAdapter
from payments.mtn_adapter import MTNAdapter
from payments.telecel_adapter import TelecelAdapter
from payments.airteltigo_adapter import AirtelTigoAdapter
from logger import logger
from data.audit_logger import AuditLogger
from config import PAYMENT_TIMEOUT_SECONDS, PAYMENT_POLL_INTERVAL
import json


class PaymentService:
    """Orchestrates payment processing for sales."""
    
    def __init__(self):
        """Initialize payment service with no shared session."""
        self.mtn_adapter = MTNAdapter()
        self.telecel_adapter = TelecelAdapter()
        self.airteltigo_adapter = AirtelTigoAdapter()
        logger.debug("PaymentService initialized")
    
    def process_cash_payment(self, sale_id: int, amount_tendered: float, cashier_id: int) -> dict:
        """
        Process cash payment.
        Returns: {"status": "completed", "change": float, "receipt_needed": True}
        """
        session = get_session()
        try:
            sale = session.query(Sale).filter_by(id=sale_id).first()
            if not sale:
                raise ValueError(f"Sale {sale_id} not found")
            
            CartService.transition_sale_state(sale_id, "processing", session)
            
            if amount_tendered < sale.total_ghs:
                raise ValueError(f"Insufficient payment. Required: {sale.total_ghs}, Tendered: {amount_tendered}")
            
            change = round(amount_tendered - sale.total_ghs, 2)
            
            payment = Payment(
                sale_id=sale_id,
                payment_method="cash",
                amount_ghs=sale.total_ghs,
                status="completed",
                paid_at=datetime.utcnow()
            )
            session.add(payment)
            
            CartService.transition_sale_state(sale_id, "completed", session)
            self._decrement_sale_stock(sale_id, session)
            
            AuditLogger.log_action(session, cashier_id, "payment_completed",
                               json.dumps({"sale_id": sale_id, "method": "cash", "amount": sale.total_ghs}))
            
            session.commit()
            logger.info(f"Cash payment processed for sale {sale_id}. Change: {change}")
            
            return {
                "status": "completed",
                "change": change,
                "receipt_needed": True
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Cash payment error: {e}")
            try:
                CartService.transition_sale_state(sale_id, "failed", session)
                AuditLogger.log_action(session, cashier_id, "payment_failed",
                                   json.dumps({"sale_id": sale_id, "method": "cash", "error": str(e)}))
                session.commit()
            except:
                session.rollback()
            raise
        finally:
            session.close()
    
    def process_card_payment(self, sale_id: int, cashier_id: int) -> dict:
        """
        Process card payment (simulated).
        Returns: {"status": "completed", "receipt_needed": True}
        """
        session = get_session()
        try:
            sale = session.query(Sale).filter_by(id=sale_id).first()
            if not sale:
                raise ValueError(f"Sale {sale_id} not found")
            
            CartService.transition_sale_state(sale_id, "processing", session)
            
            time.sleep(1)
            
            transaction_ref = f"CARD-{int(time.time())}"
            
            payment = Payment(
                sale_id=sale_id,
                payment_method="card",
                transaction_ref=transaction_ref,
                amount_ghs=sale.total_ghs,
                status="completed",
                paid_at=datetime.utcnow()
            )
            session.add(payment)
            
            CartService.transition_sale_state(sale_id, "completed", session)
            self._decrement_sale_stock(sale_id, session)
            
            AuditLogger.log_action(session, cashier_id, "payment_completed",
                               json.dumps({"sale_id": sale_id, "method": "card", "amount": sale.total_ghs}))
            
            session.commit()
            logger.info(f"Card payment processed for sale {sale_id}")
            
            return {
                "status": "completed",
                "receipt_needed": True
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Card payment error: {e}")
            try:
                CartService.transition_sale_state(sale_id, "failed", session)
                AuditLogger.log_action(session, cashier_id, "payment_failed",
                                   json.dumps({"sale_id": sale_id, "method": "card", "error": str(e)}))
                session.commit()
            except:
                session.rollback()
            raise
        finally:
            session.close()
    
    def process_mobile_money_payment(self, sale_id: int, network: str, phone: str, cashier_id: int) -> dict:
        """
        Process mobile money payment.
        Initiates payment and polls for status.
        Returns: {"status": "completed" or "failed", "receipt_needed": bool, "transaction_ref": str}
        """
        session = get_session()
        try:
            sale = session.query(Sale).filter_by(id=sale_id).first()
            if not sale:
                raise ValueError(f"Sale {sale_id} not found")
            
            adapter = self._get_adapter(network)
            
            CartService.transition_sale_state(sale_id, "processing", session)
            
            AuditLogger.log_action(session, cashier_id, "payment_initiated",
                               json.dumps({"sale_id": sale_id, "method": network, "phone": phone}))
            
            response = adapter.initiate(phone, sale.total_ghs)
            transaction_ref = response["ref"]
            
            payment = Payment(
                sale_id=sale_id,
                payment_method=network,
                mobile_money_network=network,
                customer_phone=phone,
                transaction_ref=transaction_ref,
                amount_ghs=sale.total_ghs,
                status="pending"
            )
            session.add(payment)
            session.commit()
            
            start_time = time.time()
            poll_interval = PAYMENT_POLL_INTERVAL
            timeout = PAYMENT_TIMEOUT_SECONDS
            
            logger.info(f"Polling {network} payment status: {transaction_ref}")
            
            while time.time() - start_time < timeout:
                status = adapter.poll_status(transaction_ref)
                
                if status == "SUCCESS":
                    payment.status = "completed"
                    payment.paid_at = datetime.utcnow()
                    session.commit()
                    
                    CartService.transition_sale_state(sale_id, "completed", session)
                    self._decrement_sale_stock(sale_id, session)
                    
                    AuditLogger.log_action(session, cashier_id, "payment_completed",
                                       json.dumps({"sale_id": sale_id, "method": network, "amount": sale.total_ghs}))
                    
                    session.commit()
                    logger.info(f"{network} payment completed: {transaction_ref}")
                    
                    return {
                        "status": "completed",
                        "receipt_needed": True,
                        "transaction_ref": transaction_ref
                    }
                
                elif status == "FAILED":
                    payment.status = "failed"
                    session.commit()
                    
                    CartService.transition_sale_state(sale_id, "failed", session)
                    
                    AuditLogger.log_action(session, cashier_id, "payment_failed",
                                       json.dumps({"sale_id": sale_id, "method": network, "reason": "payment_failed"}))
                    
                    session.commit()
                    logger.warning(f"{network} payment failed: {transaction_ref}")
                    
                    return {
                        "status": "failed",
                        "receipt_needed": False,
                        "transaction_ref": transaction_ref
                    }
                
                time.sleep(poll_interval)
            
            payment.status = "failed"
            session.commit()
            CartService.transition_sale_state(sale_id, "failed", session)
            
            AuditLogger.log_action(session, cashier_id, "payment_failed",
                               json.dumps({"sale_id": sale_id, "method": network, "reason": "timeout"}))
            
            session.commit()
            logger.warning(f"{network} payment timeout: {transaction_ref}")
            
            return {
                "status": "failed",
                "receipt_needed": False,
                "transaction_ref": transaction_ref
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Mobile money payment error: {e}")
            raise PaymentError(f"Mobile money payment failed: {e}")
        finally:
            session.close()
    
    def _get_adapter(self, network: str) -> MoMoAdapter:
        """Get the appropriate payment adapter."""
        if network == "mtn":
            return self.mtn_adapter
        elif network == "telecel":
            return self.telecel_adapter
        elif network == "airteltigo":
            return self.airteltigo_adapter
        else:
            raise ValueError(f"Unknown payment network: {network}")
    
    def _decrement_sale_stock(self, sale_id: int, session: Session):
        """Decrement stock for all items in a sale."""
        sale = session.query(Sale).filter_by(id=sale_id).first()
        if sale:
            for sale_item in sale.sale_items:
                InventoryService.decrement_stock(sale_item.product_id, sale_item.quantity, session)