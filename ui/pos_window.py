# ui/pos_window.py
"""
Point of Sale (POS) window for cashiers.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QRadioButton, QButtonGroup, QProgressBar, QMessageBox,
    QInputDialog, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from data.database import get_session, Sale
from logic.pos import CartService
from logic.pricing import PricingContext
from data.receipt_printer import ReceiptPrinter
from payments.payment_service import PaymentService
from payments.base import PaymentError
from logic.auth import AuthService
from logger import logger


class PaymentWorker(QThread):
    """Worker thread for processing payments."""
    success = pyqtSignal(dict)
    failure = pyqtSignal(str)
    
    def __init__(self, sale_id, method, amount, user_id, phone=None):
        super().__init__()
        self.sale_id = sale_id
        self.method = method
        self.amount = amount
        self.user_id = user_id
        self.phone = phone
    
    def run(self):
        """Execute payment processing in background thread."""
        try:
            payment_service = PaymentService()
            
            if self.method == "cash":
                result = payment_service.process_cash_payment(
                    self.sale_id, self.amount, self.user_id
                )
                self.success.emit(result)
            
            elif self.method == "card":
                payment_service.process_card_payment(
                    self.sale_id, self.user_id
                )
                self.success.emit({"status": "completed"})
            
            elif self.method in ("mtn", "telecel", "airteltigo"):
                result = payment_service.process_mobile_money_payment(
                    self.sale_id, self.method, self.phone, self.user_id
                )
                self.success.emit(result)
            
        except (ValueError, PaymentError) as e:
            self.failure.emit(str(e))
        except Exception as e:
            logger.error(f"Payment worker error: {e}")
            self.failure.emit(str(e))


class ReceiptWorker(QThread):
    """Worker thread for generating receipts."""
    success = pyqtSignal(str)
    failure = pyqtSignal(str)
    
    def __init__(self, sale_id):
        super().__init__()
        self.sale_id = sale_id
    
    def run(self):
        """Execute receipt generation in background thread."""
        session = None
        try:
            session = get_session()
            receipt_printer = ReceiptPrinter()
            receipt = receipt_printer.issue_receipt(self.sale_id, "pdf", session)
            session.commit()
            receipt_no = receipt.receipt_no
            self.success.emit(receipt_no)
        except Exception as e:
            logger.error(f"Receipt worker error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class POSWindow(QMainWindow):
    """Point of Sale window for cashiers."""
    
    window_closed = pyqtSignal()
    
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.cart_service = CartService()
        self.payment_service = PaymentService()
        self.receipt_printer = ReceiptPrinter()
        self.current_sale_id = None
        self._pending_cart_snapshot = None
        self._payment_in_progress = False
        
        self.setWindowTitle(f"Gas Mart - POS (Cashier: {user.username})")
        self.setMinimumSize(1280, 800)
        
        self._create_widgets()
        self._update_status_bar()
        logger.info(f"POS window opened for cashier {user.username}")
    
    def _run_with_session(self, fn):
        """Execute a function with a fresh session, closing it afterwards."""
        session = get_session()
        try:
            result = fn(session)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _create_widgets(self):
        """Create the POS interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)
        
        self._create_product_entry_section(left_layout)
        self._create_cart_section(left_layout)
        self._create_cart_actions(left_layout)
        
        left_panel.setLayout(left_layout)
        main_layout.addWidget(left_panel, stretch=2)
        
        right_panel = QWidget()
        right_panel.setFixedWidth(400)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)
        
        self._create_totals_section(right_layout)
        self._create_payment_section(right_layout)
        self._create_action_buttons(right_layout)
        self._create_status_bar(right_layout)
        
        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel)
        
        central_widget.setLayout(main_layout)
    
    def _create_product_entry_section(self, parent_layout):
        """Create product entry form."""
        group = QGroupBox("Add Product")
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("Product:"))
        self.barcode_entry = QLineEdit()
        self.barcode_entry.setPlaceholderText("Scan or search product")
        self.barcode_entry.returnPressed.connect(self.add_to_cart)
        layout.addWidget(self.barcode_entry)
        
        layout.addWidget(QLabel("Qty:"))
        self.qty_entry = QLineEdit("1")
        self.qty_entry.setFixedWidth(80)
        self.qty_entry.returnPressed.connect(self.add_to_cart)
        layout.addWidget(self.qty_entry)
        
        self.add_button = QPushButton("Add to Cart")
        self.add_button.clicked.connect(self.add_to_cart)
        layout.addWidget(self.add_button)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_cart_section(self, parent_layout):
        """Create cart table."""
        group = QGroupBox("Current Sale")
        layout = QVBoxLayout()
        
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(4)
        self.cart_table.setHorizontalHeaderLabels(["Item", "Qty", "Unit Price", "Line Total"])
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.cart_table)
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_cart_actions(self, parent_layout):
        """Create cart action buttons."""
        layout = QHBoxLayout()
        
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self.remove_item)
        layout.addWidget(self.remove_button)
        
        self.clear_button = QPushButton("Clear Cart")
        self.clear_button.clicked.connect(self.clear_cart)
        layout.addWidget(self.clear_button)
        
        layout.addStretch()
        
        self.item_count_label = QLabel("")
        layout.addWidget(self.item_count_label)
        
        parent_layout.addLayout(layout)
    
    def _create_totals_section(self, parent_layout):
        """Create totals display."""
        group = QGroupBox("Totals")
        layout = QGridLayout()
        
        layout.addWidget(QLabel("Subtotal:"), 0, 0)
        self.subtotal_label = QLabel("0.00")
        self.subtotal_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(self.subtotal_label, 0, 1)
        
        layout.addWidget(QLabel("Discount %:"), 1, 0)
        self.discount_entry = QLineEdit("0")
        self.discount_entry.setFixedWidth(80)
        self.discount_entry.textChanged.connect(self.update_totals)
        layout.addWidget(self.discount_entry, 1, 1)
        
        layout.addWidget(QLabel("Discount Amount:"), 2, 0)
        self.discount_amount_label = QLabel("0.00")
        layout.addWidget(self.discount_amount_label, 2, 1)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line, 3, 0, 1, 2)
        
        layout.addWidget(QLabel("TOTAL:"), 4, 0)
        self.total_label = QLabel("0.00")
        self.total_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #27ae60;")
        layout.addWidget(self.total_label, 4, 1)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_payment_section(self, parent_layout):
        """Create payment method selection."""
        group = QGroupBox("Payment Method")
        layout = QVBoxLayout()
        
        self.payment_method_group = QButtonGroup()
        methods = [
            ("Cash", "cash"),
            ("Card", "card"),
            ("MTN MoMo", "mtn"),
            ("Telecel", "telecel"),
            ("AirtelTigo", "airteltigo")
        ]
        
        for text, value in methods:
            radio = QRadioButton(text)
            radio.setObjectName(value)
            self.payment_method_group.addButton(radio)
            layout.addWidget(radio)
        
        self.payment_method_group.buttons()[0].setChecked(True)
        
        self.amount_frame = QWidget()
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("Amount Tendered:"))
        self.amount_entry = QLineEdit()
        self.amount_entry.setPlaceholderText("Enter amount")
        amount_layout.addWidget(self.amount_entry)
        self.amount_frame.setLayout(amount_layout)
        layout.addWidget(self.amount_frame)
        
        for button in self.payment_method_group.buttons():
            button.toggled.connect(self.on_payment_method_change)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_action_buttons(self, parent_layout):
        """Create payment and action buttons."""
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        parent_layout.addWidget(self.progress_bar)
        
        self.process_button = QPushButton("Process Payment")
        self.process_button.clicked.connect(self.process_payment)
        parent_layout.addWidget(self.process_button)
        
        self.print_button = QPushButton("Print Receipt")
        self.print_button.clicked.connect(self.print_receipt)
        self.print_button.setEnabled(False)
        parent_layout.addWidget(self.print_button)
        
        self.new_sale_button = QPushButton("New Sale")
        self.new_sale_button.clicked.connect(self.new_sale)
        parent_layout.addWidget(self.new_sale_button)
        
        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        parent_layout.addWidget(self.logout_button)
    
    def _create_status_bar(self, parent_layout):
        """Create status bar."""
        status_frame = QFrame()
        layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.cashier_label = QLabel(f"Cashier: {self.user.username}")
        layout.addWidget(self.cashier_label)
        
        status_frame.setLayout(layout)
        parent_layout.addWidget(status_frame)
    
    def _update_status_bar(self):
        """Update status bar with cart information."""
        item_count = len(self.cart_service.cart_items)
        if item_count == 0:
            self.status_label.setText("Ready")
            self.item_count_label.setText("")
        else:
            total_items = sum(item["qty"] for item in self.cart_service.cart_items)
            self.status_label.setText(f"Cart: {item_count} items ({total_items} units)")
            self.item_count_label.setText(f"{item_count} items")
    
    def _set_ui_processing(self, is_processing):
        """Enable/disable UI during processing."""
        self._payment_in_progress = is_processing
        
        if is_processing:
            self.progress_bar.show()
            self.process_button.setEnabled(False)
            self.new_sale_button.setEnabled(False)
            self.print_button.setEnabled(False)
            self.barcode_entry.setEnabled(False)
            self.qty_entry.setEnabled(False)
            self.discount_entry.setEnabled(False)
            self.remove_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            self.add_button.setEnabled(False)
            for button in self.payment_method_group.buttons():
                button.setEnabled(False)
        else:
            self.progress_bar.hide()
            self.process_button.setEnabled(True)
            self.new_sale_button.setEnabled(True)
            self.barcode_entry.setEnabled(True)
            self.qty_entry.setEnabled(True)
            self.discount_entry.setEnabled(True)
            self.remove_button.setEnabled(True)
            self.clear_button.setEnabled(True)
            self.add_button.setEnabled(True)
            for button in self.payment_method_group.buttons():
                button.setEnabled(True)
    
    def _set_receipt_ui(self, processing):
        """Enable/disable receipt UI."""
        self.print_button.setEnabled(not processing)
        self.new_sale_button.setEnabled(not processing)
    
    def add_to_cart(self):
        """Add item to cart."""
        if self.current_sale_id is not None:
            QMessageBox.warning(self, "Warning", "Complete or cancel current payment first.")
            return
        
        barcode = self.barcode_entry.text().strip()
        qty_str = self.qty_entry.text().strip()
        
        if not barcode:
            QMessageBox.warning(self, "Warning", "Enter a barcode or product name")
            return
        
        try:
            qty = int(qty_str) if qty_str else 1
            if qty <= 0:
                raise ValueError("Quantity must be positive")
            
            self._run_with_session(lambda s: self.cart_service.add_item(barcode, qty, s))
            self._refresh_cart_display()
            self.barcode_entry.clear()
            self.barcode_entry.setFocus()
            self._update_status_bar()
        except ValueError as e:
            QMessageBox.warning(self, "Error", f"Invalid input: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add item: {e}")
            logger.error(f"Error adding item to cart: {e}")
    
    def remove_item(self):
        """Remove selected item from cart."""
        if self.current_sale_id is not None:
            QMessageBox.warning(self, "Warning", "Cannot modify cart during payment.")
            return
        
        current_row = self.cart_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Select an item to remove")
            return
        
        if 0 <= current_row < len(self.cart_service.cart_items):
            barcode = self.cart_service.cart_items[current_row]["barcode"]
            self.cart_service.remove_item(barcode)
            self._refresh_cart_display()
            self._update_status_bar()
    
    def clear_cart(self):
        """Clear entire cart."""
        if self.current_sale_id is not None:
            QMessageBox.warning(self, "Warning", "Cannot clear cart during payment.")
            return
        
        reply = QMessageBox.question(self, "Confirm", "Clear entire cart?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.cart_service.clear_cart()
            self._refresh_cart_display()
            self._update_status_bar()
    
    def _refresh_cart_display(self):
        """Refresh cart table display."""
        self.cart_table.setRowCount(len(self.cart_service.cart_items))
        
        for i, item in enumerate(self.cart_service.cart_items):
            self.cart_table.setItem(i, 0, QTableWidgetItem(item["name"]))
            self.cart_table.setItem(i, 1, QTableWidgetItem(str(item["qty"])))
            self.cart_table.setItem(i, 2, QTableWidgetItem(f"{item['unit_price_ghs']:.2f}"))
            self.cart_table.setItem(i, 3, QTableWidgetItem(f"{item['line_total_ghs']:.2f}"))
        
        self.update_totals()
    
    def update_totals(self):
        """Update totals display."""
        try:
            discount_percent = float(self.discount_entry.text() or 0)
            self.cart_service.apply_discount(discount_percent)
        except ValueError:
            self.cart_service.apply_discount(0)
        
        totals = self.cart_service.get_totals()
        self.subtotal_label.setText(f"{totals['subtotal']:.2f}")
        self.discount_amount_label.setText(f"{totals['discount_amount']:.2f}")
        self.total_label.setText(f"{totals['total_ghs']:.2f}")
    
    def on_payment_method_change(self):
        """Handle payment method change."""
        method = self.payment_method_group.checkedButton().objectName()
        self.amount_frame.setVisible(method == "cash")
    
    def _restore_cart_from_snapshot(self):
        """Restore cart from snapshot after failed payment."""
        if self._pending_cart_snapshot is None:
            return
        
        self.cart_service.cart_items = list(self._pending_cart_snapshot["items"])
        self.cart_service._discount_percent = self._pending_cart_snapshot["discount_percent"]
        
        if self.current_sale_id is not None:
            sale_id = self.current_sale_id
            try:
                self._run_with_session(lambda s: self._void_failed_sale(s, sale_id))
            except Exception as void_err:
                logger.error(f"Could not void sale {self.current_sale_id}: {void_err}")
        
        self.current_sale_id = None
        self._pending_cart_snapshot = None
        self._refresh_cart_display()
        self._update_status_bar()
    
    def _void_failed_sale(self, session, sale_id):
        """Void a failed sale."""
        sale = session.query(Sale).filter_by(id=sale_id).first()
        if sale and sale.status in ("pending", "processing", "failed"):
            session.delete(sale)
            session.commit()
            logger.info(f"Voided failed sale {sale_id}")
    
    def process_payment(self):
        """Process payment in worker thread."""
        if self._payment_in_progress:
            return
        
        if not self.cart_service.cart_items and self.current_sale_id is None:
            QMessageBox.warning(self, "Warning", "Cart is empty")
            return
        
        method = self.payment_method_group.checkedButton().objectName()
        amount = None
        
        if method == "cash":
            amount_str = self.amount_entry.text().strip()
            if not amount_str:
                QMessageBox.warning(self, "Warning", "Enter amount tendered")
                return
            try:
                amount = float(amount_str)
            except ValueError:
                QMessageBox.critical(self, "Error", "Amount must be a number")
                return
        
        if self.current_sale_id is None:
            try:
                self._pending_cart_snapshot = {
                    "items": list(self.cart_service.cart_items),
                    "discount_percent": self.cart_service._discount_percent,
                }
                self.current_sale_id = self._run_with_session(
                    lambda s: self.cart_service.commit_sale(self.user.id, s)
                )
            except Exception as e:
                self._pending_cart_snapshot = None
                QMessageBox.critical(self, "Error", f"Failed to create sale: {e}")
                logger.error(f"commit_sale error: {e}")
                return
        
        phone = None
        if method in ("mtn", "telecel", "airteltigo"):
            phone, ok = QInputDialog.getText(self, "Mobile Money", 
                                              f"Enter phone number for {method.upper()}:")
            if not ok or not phone:
                self._restore_cart_from_snapshot()
                self.status_label.setText("Payment cancelled. Cart restored.")
                return
        
        self._set_ui_processing(True)
        self.status_label.setText("Processing payment...")
        
        self.payment_worker = PaymentWorker(
            self.current_sale_id, method, amount, self.user.id, phone
        )
        self.payment_worker.success.connect(self._on_payment_success, Qt.ConnectionType.QueuedConnection)
        self.payment_worker.failure.connect(self._on_payment_failure, Qt.ConnectionType.QueuedConnection)
        self.payment_worker.start()
    
    def _on_payment_success(self, result):
        """Handle successful payment."""
        logger.debug(f"Payment success")
        self._pending_cart_snapshot = None
        self._payment_in_progress = False
        
        self.process_button.setEnabled(False)
        self.print_button.setEnabled(True)
        self.barcode_entry.setEnabled(False)
        self.qty_entry.setEnabled(False)
        self.discount_entry.setEnabled(False)
        self.add_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        for button in self.payment_method_group.buttons():
            button.setEnabled(False)
        
        self.progress_bar.hide()
        self.status_label.setText("Payment completed. Ready to print receipt.")
        
        if "change" in result:
            QMessageBox.information(self, "Payment Successful", f"Change: {result['change']:.2f} GHS")
        elif "transaction_ref" in result:
            QMessageBox.information(self, "Payment Successful", f"Ref: {result['transaction_ref']}")
        else:
            QMessageBox.information(self, "Payment Successful", "Payment completed successfully")
    
    def _on_payment_failure(self, message):
        """Handle failed payment."""
        logger.debug(f"Payment failure: {message}")
        self._restore_cart_from_snapshot()
        self._set_ui_processing(False)
        self.status_label.setText("Payment failed. Cart restored.")
        QMessageBox.critical(self, "Payment Failed", f"{message}\n\nCart restored.")
    
    def print_receipt(self):
        """Print receipt in worker thread."""
        logger.debug("print_receipt called")
        if self._payment_in_progress:
            logger.debug("Print receipt blocked: payment in progress")
            return
        if not self.current_sale_id:
            QMessageBox.warning(self, "Warning", "No completed sale to print receipt for")
            return
        
        self._set_receipt_ui(processing=True)
        
        self.receipt_worker = ReceiptWorker(self.current_sale_id)
        self.receipt_worker.success.connect(self._on_receipt_success, Qt.ConnectionType.QueuedConnection)
        self.receipt_worker.failure.connect(self._on_receipt_failure, Qt.ConnectionType.QueuedConnection)
        self.receipt_worker.start()
    
    def _on_receipt_success(self, receipt_no):
        """Handle successful receipt printing."""
        self._set_receipt_ui(processing=False)
        QMessageBox.information(self, "Success", f"Receipt printed: {receipt_no}")
        self.new_sale()
    
    def _on_receipt_failure(self, message):
        """Handle failed receipt printing."""
        self._set_receipt_ui(processing=False)
        QMessageBox.critical(self, "Error", f"Failed to print receipt: {message}")
    
    def new_sale(self):
        """Start a new sale."""
        logger.debug("new_sale called")
        self.cart_service.clear_cart()
        self.current_sale_id = None
        self._pending_cart_snapshot = None
        self._payment_in_progress = False
        
        self.barcode_entry.clear()
        self.qty_entry.setText("1")
        self.discount_entry.setText("0")
        self.amount_entry.clear()
        
        self._refresh_cart_display()
        self.barcode_entry.setFocus()
        self._update_status_bar()
        
        self.progress_bar.hide()
        
        self.process_button.setEnabled(True)
        self.print_button.setEnabled(False)
        self.barcode_entry.setEnabled(True)
        self.qty_entry.setEnabled(True)
        self.discount_entry.setEnabled(True)
        self.add_button.setEnabled(True)
        self.remove_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        for button in self.payment_method_group.buttons():
            button.setEnabled(True)
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.window_closed.emit()
        super().closeEvent(event)
    
    def logout(self):
        """Logout user and close window."""
        try:
            self._run_with_session(lambda s: AuthService.logout(self.user.id, s))
        except Exception as e:
            logger.error(f"Logout error: {e}")
        finally:
            self.close()