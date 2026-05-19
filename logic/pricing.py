"""
Pricing strategy pattern implementation.
"""
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from data.database import Product, PriceListMode
from logger import logger
from data.audit_logger import AuditLogger
import json


class PriceStrategy(ABC):
    """Abstract base class for pricing strategies."""
    
    @abstractmethod
    def get_price(self, barcode: str, session: Session) -> float:
        """Get price for a product by barcode."""
        pass


class DemoPriceStrategy(PriceStrategy):
    """Pricing strategy using demo prices."""
    
    def get_price(self, barcode: str, session: Session) -> float:
        """Get demo price for a product."""
        product = session.query(Product).filter_by(barcode=barcode).first()
        if not product:
            raise ValueError(f"Product with barcode '{barcode}' not found")
        return product.demo_price


class RealPriceStrategy(PriceStrategy):
    """Pricing strategy using real prices."""
    
    def get_price(self, barcode: str, session: Session) -> float:
        """Get real price for a product. Raises error if real_price not set."""
        product = session.query(Product).filter_by(barcode=barcode).first()
        if not product:
            raise ValueError(f"Product with barcode '{barcode}' not found")
        if product.real_price is None:
            raise ValueError(f"Real price not set for product '{product.name}' (barcode: {barcode})")
        return product.real_price


class PricingContext:
    """Context for pricing strategies. Reads price_list_mode and instantiates appropriate strategy."""
    
    def __init__(self, session: Session):
        """Initialize pricing context. Reads current price mode from database."""
        self.session = session
        self.mode_record = session.query(PriceListMode).first()
        if not self.mode_record:
            raise RuntimeError("Price list mode not initialized in database")
        self.current_mode = self.mode_record.mode
        
        if self.current_mode == "demo":
            self.strategy = DemoPriceStrategy()
        elif self.current_mode == "real":
            self.strategy = RealPriceStrategy()
        else:
            raise ValueError(f"Unknown price mode: {self.current_mode}")
        
        logger.debug(f"PricingContext initialized with mode: {self.current_mode}")
    
    def get_price(self, barcode: str) -> float:
        """Get price for a product using current strategy."""
        return self.strategy.get_price(barcode, self.session)
    
    @staticmethod
    def activate_real_prices(admin_user_id: int, session: Session):
        """Activate real pricing. Validates all real_prices set first."""
        try:
            # Check if all products have real_price set
            products_without_real_price = session.query(Product).filter(Product.real_price.is_(None)).all()
            if products_without_real_price:
                product_names = [p.name for p in products_without_real_price[:5]]
                raise ValueError(
                    f"Cannot activate real prices. Missing real_price for {len(products_without_real_price)} products. "
                    f"Examples: {', '.join(product_names)}"
                )
            
            # Update mode
            mode_record = session.query(PriceListMode).first()
            mode_record.mode = "real"
            session.commit()
            
            # Audit log
            AuditLogger.log_action(session, admin_user_id, "price_mode_switched_real",
                               json.dumps({"previous_mode": "demo"}))
            
            logger.info(f"Real pricing activated by user {admin_user_id}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error activating real prices: {e}")
            raise
    
    @staticmethod
    def activate_demo_prices(admin_user_id: int, session: Session):
        """Revert to demo pricing."""
        try:
            mode_record = session.query(PriceListMode).first()
            previous_mode = mode_record.mode
            mode_record.mode = "demo"
            session.commit()
            
            AuditLogger.log_action(session, admin_user_id, "price_mode_switched_demo",
                               json.dumps({"previous_mode": previous_mode}))
            
            logger.info(f"Demo pricing activated by user {admin_user_id}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error activating demo prices: {e}")
            raise