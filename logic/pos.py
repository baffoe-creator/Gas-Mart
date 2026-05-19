"""
Point of Sale and Inventory management services.
"""
from sqlalchemy.orm import Session
from data.database import Product, InventoryAlert, Sale, SaleItem, User
from logger import logger
from data.audit_logger import AuditLogger
from datetime import datetime
import json


class InvalidStateError(Exception):
    """Raised when an operation is attempted in an invalid state."""
    pass


class CartService:
    """Service for managing shopping cart and sales."""

    def __init__(self):
        # No session stored — all DB operations receive a session from the caller
        self.cart_items = []
        self._discount_percent = 0.0

    def add_item(self, barcode: str, quantity: int, session: Session):
        """Add item to cart by barcode or partial name."""
        product = session.query(Product).filter_by(barcode=barcode).first()
        if not product:
            product = session.query(Product).filter(
                Product.name.ilike(f"%{barcode}%")
            ).first()
        if not product:
            raise ValueError(f"Product '{barcode}' not found")

        if product.stock_qty < quantity:
            raise ValueError(f"Insufficient stock. Available: {product.stock_qty}")

        for item in self.cart_items:
            if item['product_id'] == product.id:
                item['qty'] += quantity
                item['line_total_ghs'] = item['qty'] * item['unit_price_ghs']
                return

        self.cart_items.append({
            'product_id': product.id,
            'barcode': product.barcode,
            'name': product.name,
            'qty': quantity,
            'unit_price_ghs': product.demo_price,
            'line_total_ghs': quantity * product.demo_price
        })

    def remove_item(self, barcode: str):
        """Remove item from cart by barcode. Pure in-memory, no session needed."""
        self.cart_items = [item for item in self.cart_items if item['barcode'] != barcode]

    def update_quantity(self, barcode: str, quantity: int):
        """Update item quantity. Pure in-memory, no session needed."""
        for item in self.cart_items:
            if item['barcode'] == barcode:
                if quantity <= 0:
                    self.remove_item(barcode)
                else:
                    item['qty'] = quantity
                    item['line_total_ghs'] = quantity * item['unit_price_ghs']
                return

    def apply_discount(self, discount_percent: float):
        """Store discount percentage for use in get_totals."""
        self._discount_percent = max(0.0, min(discount_percent, 100.0))

    def get_totals(self) -> dict:
        """Return subtotal, discount amount, and total."""
        subtotal = sum(item['line_total_ghs'] for item in self.cart_items)
        discount_amount = subtotal * (self._discount_percent / 100)
        total = subtotal - discount_amount
        return {
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'total_ghs': total
        }

    def get_subtotal(self) -> float:
        """Calculate subtotal."""
        return sum(item['line_total_ghs'] for item in self.cart_items)

    def get_total(self, discount: float = 0) -> float:
        """Calculate total with discount."""
        return self.get_subtotal() - discount

    def clear_cart(self):
        """Clear all items from cart."""
        self.cart_items = []
        self._discount_percent = 0.0

    def commit_sale(self, cashier_id: int, session: Session) -> int:
        """Commit cart to database as a sale. Returns new sale ID."""
        if not self.cart_items:
            raise InvalidStateError("Cannot commit empty cart")

        totals = self.get_totals()

        sale = Sale(
            cashier_id=cashier_id,
            status="pending",
            subtotal=totals['subtotal'],
            discount=totals['discount_amount'],
            total_ghs=totals['total_ghs'],
            created_at=datetime.utcnow()
        )
        session.add(sale)
        session.flush()

        for item in self.cart_items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item['product_id'],
                quantity=item['qty'],
                unit_price_ghs=item['unit_price_ghs'],
                line_total_ghs=item['line_total_ghs']
            )
            session.add(sale_item)

        session.commit()
        logger.info(f"Sale {sale.id} created with {len(self.cart_items)} items")
        self.clear_cart()
        return sale.id

    @staticmethod
    def transition_sale_state(sale_id: int, new_state: str, session: Session):
        """Transition a sale to a new state."""
        valid_states = ["cart", "pending", "processing", "completed", "failed", "receipt_issued"]
        if new_state not in valid_states:
            raise ValueError(f"Invalid state: {new_state}")

        sale = session.query(Sale).filter_by(id=sale_id).first()
        if not sale:
            raise ValueError(f"Sale with id {sale_id} not found")

        old_state = sale.status
        sale.status = new_state
        session.commit()
        logger.debug(f"Sale {sale_id} transitioned: {old_state} -> {new_state}")

    @staticmethod
    def get_sale(sale_id: int, session: Session) -> Sale:
        """Get a sale by ID."""
        sale = session.query(Sale).filter_by(id=sale_id).first()
        if not sale:
            raise ValueError(f"Sale with id {sale_id} not found")
        return sale


class InventoryService:
    """Service for inventory management."""

    @staticmethod
    def decrement_stock(product_id: int, quantity: int, session: Session):
        """Decrement product stock. Raises ValueError if insufficient stock."""
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Product with id {product_id} not found")

            if product.stock_qty < quantity:
                raise ValueError(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock_qty}, Requested: {quantity}"
                )

            product.stock_qty -= quantity
            session.commit()
            logger.debug(f"Stock decremented for product {product.id}: -{quantity}")
            InventoryService.check_low_stock(product_id, session)

        except Exception as e:
            session.rollback()
            logger.error(f"Error decrementing stock: {e}")
            raise

    @staticmethod
    def increment_stock(product_id: int, quantity: int, session: Session):
        """Increment product stock."""
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Product with id {product_id} not found")

            product.stock_qty += quantity
            session.commit()
            logger.info(f"Stock incremented for product {product.id}: +{quantity}")

        except Exception as e:
            session.rollback()
            logger.error(f"Error incrementing stock: {e}")
            raise

    @staticmethod
    def check_low_stock(product_id: int, session: Session):
        """Check if product stock is below threshold and create alert if so."""
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Product with id {product_id} not found")

            existing_alert = session.query(InventoryAlert).filter_by(
                product_id=product_id,
                is_resolved=False
            ).first()

            if product.stock_qty <= product.reorder_threshold and not existing_alert:
                alert = InventoryAlert(
                    product_id=product_id,
                    qty_at_alert=product.stock_qty
                )
                session.add(alert)
                session.commit()
                logger.warning(
                    f"Low stock alert created for '{product.name}' "
                    f"(current: {product.stock_qty}, threshold: {product.reorder_threshold})"
                )

        except Exception as e:
            session.rollback()
            logger.error(f"Error checking low stock: {e}")

    @staticmethod
    def resolve_alert(alert_id: int, session: Session):
        """Mark an inventory alert as resolved."""
        try:
            alert = session.query(InventoryAlert).filter_by(id=alert_id).first()
            if not alert:
                raise ValueError(f"Alert with id {alert_id} not found")

            alert.is_resolved = True
            session.commit()
            logger.info(f"Inventory alert {alert_id} marked as resolved")

        except Exception as e:
            session.rollback()
            logger.error(f"Error resolving alert: {e}")
            raise

    @staticmethod
    def update_product_price(product_id: int, real_price: float, session: Session):
        """Update product's real price."""
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Product with id {product_id} not found")

            old_price = product.real_price
            product.real_price = real_price
            session.commit()
            logger.info(f"Product '{product.name}' real_price updated: {old_price} -> {real_price}")

        except Exception as e:
            session.rollback()
            logger.error(f"Error updating product price: {e}")
            raise

    @staticmethod
    def add_product(barcode: str, name: str, category: str, demo_price: float,
                    stock_qty: int, reorder_threshold: int, session: Session) -> Product:
        """Add a new product."""
        try:
            existing = session.query(Product).filter_by(barcode=barcode).first()
            if existing:
                raise ValueError(f"Product with barcode '{barcode}' already exists")

            product = Product(
                barcode=barcode,
                name=name,
                category=category,
                demo_price=demo_price,
                real_price=None,
                stock_qty=stock_qty,
                reorder_threshold=reorder_threshold
            )
            session.add(product)
            session.commit()
            logger.info(f"New product added: '{name}' (barcode: {barcode})")
            return product

        except Exception as e:
            session.rollback()
            logger.error(f"Error adding product: {e}")
            raise

    @staticmethod
    def get_low_stock_products(session: Session) -> list:
        """Get all products currently below reorder threshold."""
        return session.query(Product).filter(
            Product.stock_qty <= Product.reorder_threshold
        ).all()