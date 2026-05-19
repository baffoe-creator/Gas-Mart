# ui/inventory_panel.py
"""
Inventory management panel for managers and admins.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QTabWidget, QComboBox, QProgressBar, QMessageBox,
    QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from data.database import get_session, Product, InventoryAlert
from logic.inventory import InventoryService
from logic.auth import AuthService
from logger import logger
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta


class ProductLoadWorker(QThread):
    """Worker thread for loading products."""
    success = pyqtSignal(list)
    failure = pyqtSignal(str)
    
    def __init__(self, search_term="", category_filter="All"):
        super().__init__()
        self.search_term = search_term.lower()
        self.category_filter = category_filter
    
    def run(self):
        """Load products in background thread."""
        session = None
        try:
            session = get_session()
            products = session.query(Product).all()
            session.commit()
            
            filtered = []
            for product in products:
                if self.search_term and self.search_term not in product.name.lower():
                    continue
                if self.category_filter != "All" and product.category != self.category_filter:
                    continue
                filtered.append(product)
            
            self.success.emit(filtered)
        except Exception as e:
            logger.error(f"Product load error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class AddProductWorker(QThread):
    """Worker thread for adding a product."""
    success = pyqtSignal(str)
    failure = pyqtSignal(str)
    
    def __init__(self, barcode, name, category, demo_price, real_price, stock, threshold):
        super().__init__()
        self.barcode = barcode
        self.name = name
        self.category = category
        self.demo_price = demo_price
        self.real_price = real_price
        self.stock = stock
        self.threshold = threshold
    
    def run(self):
        """Add product in background thread."""
        session = None
        try:
            session = get_session()
            
            existing = session.query(Product).filter_by(barcode=self.barcode).first()
            if existing:
                self.failure.emit(f"Product with barcode '{self.barcode}' already exists")
                return
            
            product = InventoryService.add_product(
                self.barcode, self.name, self.category, 
                self.demo_price, self.stock, self.threshold, session
            )
            
            if self.real_price:
                product.real_price = self.real_price
                session.commit()
            
            self.success.emit(product.name)
        except ValueError as e:
            self.failure.emit(str(e))
        except Exception as e:
            logger.error(f"Add product error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class UpdateProductWorker(QThread):
    """Worker thread for updating a product."""
    success = pyqtSignal()
    failure = pyqtSignal(str)
    
    def __init__(self, product_id, name, category, stock, threshold, real_price):
        super().__init__()
        self.product_id = product_id
        self.name = name
        self.category = category
        self.stock = stock
        self.threshold = threshold
        self.real_price = real_price
    
    def run(self):
        """Update product in background thread."""
        session = None
        try:
            session = get_session()
            product = session.query(Product).filter_by(id=self.product_id).first()
            if not product:
                self.failure.emit("Product not found")
                return
            
            product.name = self.name
            product.category = self.category
            product.stock_qty = self.stock
            product.reorder_threshold = self.threshold
            
            if self.real_price is not None:
                product.real_price = self.real_price
            
            session.commit()
            self.success.emit()
        except Exception as e:
            logger.error(f"Update product error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class DeleteProductWorker(QThread):
    """Worker thread for deleting a product."""
    success = pyqtSignal(str)
    failure = pyqtSignal(str)
    
    def __init__(self, product_id):
        super().__init__()
        self.product_id = product_id
    
    def run(self):
        """Delete product in background thread."""
        session = None
        try:
            session = get_session()
            product = session.query(Product).filter_by(id=self.product_id).first()
            if not product:
                self.failure.emit("Product not found")
                return
            
            product_name = product.name
            session.delete(product)
            session.commit()
            self.success.emit(product_name)
        except Exception as e:
            logger.error(f"Delete product error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class AlertLoadWorker(QThread):
    """Worker thread for loading alerts."""
    success = pyqtSignal(list)
    failure = pyqtSignal(str)
    
    def run(self):
        """Load alerts in background thread."""
        session = None
        try:
            session = get_session()
            alerts = session.query(InventoryAlert)\
                .options(joinedload(InventoryAlert.product))\
                .filter_by(is_resolved=False).all()
            session.commit()
            self.success.emit(alerts)
        except Exception as e:
            logger.error(f"Alert load error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class ResolveAlertWorker(QThread):
    """Worker thread for resolving an alert."""
    success = pyqtSignal()
    failure = pyqtSignal(str)
    
    def __init__(self, product_name):
        super().__init__()
        self.product_name = product_name
    
    def run(self):
        """Resolve alert in background thread."""
        session = None
        try:
            session = get_session()
            product = session.query(Product).filter_by(name=self.product_name).first()
            if product:
                alert = session.query(InventoryAlert).filter_by(
                    product_id=product.id, is_resolved=False
                ).first()
                if alert:
                    InventoryService.resolve_alert(alert.id, session)
                    session.commit()
            self.success.emit()
        except Exception as e:
            logger.error(f"Resolve alert error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class InventoryWindow(QMainWindow):
    """Inventory management window for managers and admins."""
    
    window_closed = pyqtSignal()
    
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.selected_product_id = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._refresh_products)
        
        self.setWindowTitle(f"Gas Mart - Inventory ({user.username})")
        self.setMinimumSize(1200, 900)
        
        self._create_widgets()
        self._refresh_products()
        self._refresh_alerts()
        
        logger.info(f"Inventory panel opened for {user.username}")
    
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
        """Create inventory panel widgets."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.tab_widget = QTabWidget()
        
        products_tab = QWidget()
        self._create_products_tab(products_tab)
        self.tab_widget.addTab(products_tab, "Products")
        
        alerts_tab = QWidget()
        self._create_alerts_tab(alerts_tab)
        self.tab_widget.addTab(alerts_tab, "Stock Alerts")
        
        add_tab = QWidget()
        self._create_add_product_tab(add_tab)
        self.tab_widget.addTab(add_tab, "Add Product")
        
        layout.addWidget(self.tab_widget)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        layout.addWidget(self.logout_button)
        
        central_widget.setLayout(layout)
    
    def _create_products_tab(self, parent):
        """Create products management tab."""
        layout = QVBoxLayout()
        
        search_frame = QGroupBox("Search & Filter")
        search_layout = QHBoxLayout()
        
        search_layout.addWidget(QLabel("Search by Name:"))
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Enter product name...")
        self.search_entry.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_entry)
        
        search_layout.addWidget(QLabel("Filter by Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("All")
        self.category_combo.currentTextChanged.connect(lambda: self._refresh_products())
        search_layout.addWidget(self.category_combo)
        
        self.reset_button = QPushButton("Reset Filter")
        self.reset_button.clicked.connect(self._reset_search)
        search_layout.addWidget(self.reset_button)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_products)
        search_layout.addWidget(self.refresh_button)
        
        search_frame.setLayout(search_layout)
        layout.addWidget(search_frame)
        
        products_frame = QGroupBox("Products Inventory")
        products_layout = QVBoxLayout()
        
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(8)
        self.products_table.setHorizontalHeaderLabels([
            "Barcode", "Name", "Category", "Stock", "Threshold", "Demo Price", "Real Price", "Status"
        ])
        self.products_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.products_table.itemSelectionChanged.connect(self._on_product_selected)
        products_layout.addWidget(self.products_table)
        
        products_frame.setLayout(products_layout)
        layout.addWidget(products_frame)
        
        edit_frame = QGroupBox("Edit Selected Product")
        edit_layout = QGridLayout()
        
        edit_layout.addWidget(QLabel("Product Name:"), 0, 0)
        self.name_entry = QLineEdit()
        edit_layout.addWidget(self.name_entry, 0, 1)
        
        edit_layout.addWidget(QLabel("Barcode:"), 0, 2)
        self.barcode_label = QLabel("N/A")
        edit_layout.addWidget(self.barcode_label, 0, 3)
        
        edit_layout.addWidget(QLabel("Category:"), 1, 0)
        self.cat_entry = QLineEdit()
        edit_layout.addWidget(self.cat_entry, 1, 1)
        
        edit_layout.addWidget(QLabel("Reorder Threshold:"), 1, 2)
        self.threshold_entry = QLineEdit()
        edit_layout.addWidget(self.threshold_entry, 1, 3)
        
        edit_layout.addWidget(QLabel("Stock Qty:"), 2, 0)
        self.stock_entry = QLineEdit()
        edit_layout.addWidget(self.stock_entry, 2, 1)
        
        edit_layout.addWidget(QLabel("Real Price (GHS):"), 2, 2)
        self.price_entry = QLineEdit()
        edit_layout.addWidget(self.price_entry, 2, 3)
        
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Changes")
        self.save_button.clicked.connect(self.save_product_changes)
        button_layout.addWidget(self.save_button)
        
        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(self.clear_selection)
        button_layout.addWidget(self.clear_button)
        
        self.delete_button = QPushButton("Delete Product")
        self.delete_button.clicked.connect(self.delete_product)
        button_layout.addWidget(self.delete_button)
        
        edit_layout.addLayout(button_layout, 3, 0, 1, 4)
        
        edit_frame.setLayout(edit_layout)
        layout.addWidget(edit_frame)
        
        parent.setLayout(layout)
    
    def _create_alerts_tab(self, parent):
        """Create stock alerts tab."""
        layout = QVBoxLayout()
        
        summary_frame = QGroupBox("Low Stock Summary")
        summary_layout = QHBoxLayout()
        
        self.alert_count_label = QLabel("Total Unresolved Alerts: 0")
        self.alert_count_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        summary_layout.addWidget(self.alert_count_label)
        
        summary_layout.addStretch()
        
        self.refresh_alerts_button = QPushButton("Refresh")
        self.refresh_alerts_button.clicked.connect(self._refresh_alerts)
        summary_layout.addWidget(self.refresh_alerts_button)
        
        summary_frame.setLayout(summary_layout)
        layout.addWidget(summary_frame)
        
        alerts_frame = QGroupBox("Active Stock Alerts")
        alerts_layout = QVBoxLayout()
        
        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(6)
        self.alerts_table.setHorizontalHeaderLabels([
            "Product", "Barcode", "Current Stock", "Threshold", "Triggered At", "Days Ago"
        ])
        self.alerts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.alerts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        alerts_layout.addWidget(self.alerts_table)
        
        alerts_frame.setLayout(alerts_layout)
        layout.addWidget(alerts_frame)
        
        button_layout = QHBoxLayout()
        
        self.resolve_button = QPushButton("Mark Selected as Resolved")
        self.resolve_button.clicked.connect(self.resolve_alert)
        button_layout.addWidget(self.resolve_button)
        
        self.resolve_all_button = QPushButton("Mark All as Resolved")
        self.resolve_all_button.clicked.connect(self.resolve_all_alerts)
        button_layout.addWidget(self.resolve_all_button)
        
        layout.addLayout(button_layout)
        
        parent.setLayout(layout)
    
    def _create_add_product_tab(self, parent):
        """Create add new product tab."""
        layout = QVBoxLayout()
        
        form_frame = QGroupBox("Add New Product")
        form_layout = QGridLayout()
        form_layout.setSpacing(15)
        
        form_layout.addWidget(QLabel("Barcode:"), 0, 0)
        self.new_barcode_entry = QLineEdit()
        form_layout.addWidget(self.new_barcode_entry, 0, 1)
        
        form_layout.addWidget(QLabel("Product Name:"), 1, 0)
        self.new_name_entry = QLineEdit()
        form_layout.addWidget(self.new_name_entry, 1, 1)
        
        form_layout.addWidget(QLabel("Category:"), 2, 0)
        self.new_category_entry = QLineEdit()
        form_layout.addWidget(self.new_category_entry, 2, 1)
        
        form_layout.addWidget(QLabel("Demo Price (GHS):"), 3, 0)
        self.new_demo_price_entry = QLineEdit()
        form_layout.addWidget(self.new_demo_price_entry, 3, 1)
        
        form_layout.addWidget(QLabel("Real Price (GHS):"), 0, 2)
        self.new_real_price_entry = QLineEdit()
        form_layout.addWidget(self.new_real_price_entry, 0, 3)
        
        form_layout.addWidget(QLabel("Initial Stock Qty:"), 1, 2)
        self.new_stock_entry = QLineEdit("50")
        form_layout.addWidget(self.new_stock_entry, 1, 3)
        
        form_layout.addWidget(QLabel("Reorder Threshold:"), 2, 2)
        self.new_threshold_entry = QLineEdit("10")
        form_layout.addWidget(self.new_threshold_entry, 2, 3)
        
        info_label = QLabel("All fields required except 'Real Price' (can be set later)")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        form_layout.addWidget(info_label, 4, 0, 1, 4)
        
        button_layout = QHBoxLayout()
        self.add_product_button = QPushButton("Add Product")
        self.add_product_button.clicked.connect(self.add_new_product)
        button_layout.addWidget(self.add_product_button)
        
        self.clear_form_button = QPushButton("Clear Form")
        self.clear_form_button.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_form_button)
        
        form_layout.addLayout(button_layout, 5, 0, 1, 4)
        
        form_frame.setLayout(form_layout)
        layout.addWidget(form_frame)
        layout.addStretch()
        
        parent.setLayout(layout)
        
        self._populate_categories()
    
    def _populate_categories(self):
        """Populate category dropdown."""
        def query(session):
            categories = session.query(Product.category).distinct().all()
            return ["All"] + [cat[0] for cat in categories if cat[0]]
        
        try:
            cat_list = self._run_with_session(query)
            self.category_combo.clear()
            self.category_combo.addItems(cat_list)
        except Exception as e:
            logger.error(f"Error populating categories: {e}")
    
    def _show_processing(self, show):
        """Show/hide progress bar."""
        if show:
            self.progress_bar.show()
            self.tab_widget.setEnabled(False)
            self.logout_button.setEnabled(False)
        else:
            self.progress_bar.hide()
            self.tab_widget.setEnabled(True)
            self.logout_button.setEnabled(True)
    
    def _refresh_products(self):
        """Refresh products list with search and filter."""
        self._show_processing(True)
        
        search_term = self.search_entry.text()
        category_filter = self.category_combo.currentText()
        
        self.product_worker = ProductLoadWorker(search_term, category_filter)
        self.product_worker.success.connect(self._on_products_loaded, Qt.ConnectionType.QueuedConnection)
        self.product_worker.failure.connect(self._on_products_load_failed, Qt.ConnectionType.QueuedConnection)
        self.product_worker.start()
    
    def _on_products_loaded(self, products):
        """Handle loaded products."""
        self.products_table.setRowCount(0)
        
        for product in products:
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            
            if product.stock_qty <= product.reorder_threshold:
                status = "🔴 LOW"
                status_color = "#cc0000"
            elif product.stock_qty <= product.reorder_threshold * 1.5:
                status = "🟡 MEDIUM"
                status_color = "#e67e22"
            else:
                status = "🟢 OK"
                status_color = "#27ae60"
            
            self.products_table.setItem(row, 0, QTableWidgetItem(product.barcode))
            self.products_table.setItem(row, 1, QTableWidgetItem(product.name))
            self.products_table.setItem(row, 2, QTableWidgetItem(product.category))
            self.products_table.setItem(row, 3, QTableWidgetItem(str(product.stock_qty)))
            self.products_table.setItem(row, 4, QTableWidgetItem(str(product.reorder_threshold)))
            self.products_table.setItem(row, 5, QTableWidgetItem(f"{product.demo_price:.2f}"))
            self.products_table.setItem(row, 6, QTableWidgetItem(f"{product.real_price:.2f}" if product.real_price else "N/A"))
            
            status_item = QTableWidgetItem(status)
            status_item.setForeground(Qt.GlobalColor.red if "LOW" in status else 
                                     Qt.GlobalColor.darkYellow if "MEDIUM" in status else
                                     Qt.GlobalColor.green)
            self.products_table.setItem(row, 7, status_item)
        
        self._show_processing(False)
    
    def _on_products_load_failed(self, error):
        """Handle product load failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to load products: {error}")
        logger.error(f"Error loading products: {error}")
    
    def _reset_search(self):
        """Reset search and filter."""
        self.search_entry.clear()
        self.category_combo.setCurrentIndex(0)
    
    def _on_search_changed(self):
        """Handle search input with debouncing."""
        self._search_timer.start(300)
    
    def _on_product_selected(self):
        """Handle product selection."""
        selected = self.products_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        barcode = self.products_table.item(row, 0).text()
        
        def query(session):
            return session.query(Product).filter_by(barcode=barcode).first()
        
        try:
            product = self._run_with_session(query)
            if product:
                self.selected_product_id = product.id
                self.barcode_label.setText(product.barcode)
                self.name_entry.setText(product.name)
                self.cat_entry.setText(product.category)
                self.stock_entry.setText(str(product.stock_qty))
                self.threshold_entry.setText(str(product.reorder_threshold))
                self.price_entry.setText(f"{product.real_price:.2f}" if product.real_price else "")
        except Exception as e:
            logger.error(f"Error loading product details: {e}")
    
    def clear_selection(self):
        """Clear all edit fields."""
        self.selected_product_id = None
        self.barcode_label.setText("N/A")
        self.name_entry.clear()
        self.cat_entry.clear()
        self.stock_entry.clear()
        self.threshold_entry.clear()
        self.price_entry.clear()
        self.products_table.clearSelection()
    
    def save_product_changes(self):
        """Save changes to selected product."""
        if not self.selected_product_id:
            QMessageBox.warning(self, "Warning", "Please select a product first")
            return
        
        try:
            name = self.name_entry.text().strip()
            category = self.cat_entry.text().strip()
            stock = int(self.stock_entry.text().strip())
            threshold = int(self.threshold_entry.text().strip())
            price_str = self.price_entry.text().strip()
            real_price = float(price_str) if price_str else None
            
            if not name or not category:
                QMessageBox.warning(self, "Warning", "Name and category are required")
                return
            
            if stock < 0 or threshold < 0:
                QMessageBox.critical(self, "Error", "Stock and threshold cannot be negative")
                return
            
            self._show_processing(True)
            
            self.update_worker = UpdateProductWorker(
                self.selected_product_id, name, category, stock, threshold, real_price
            )
            self.update_worker.success.connect(self._on_update_success, Qt.ConnectionType.QueuedConnection)
            self.update_worker.failure.connect(self._on_update_failure, Qt.ConnectionType.QueuedConnection)
            self.update_worker.start()
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Invalid input: {e}")
    
    def _on_update_success(self):
        """Handle successful product update."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", "Product updated successfully")
        self._refresh_products()
        self.clear_selection()
        self._populate_categories()
        logger.info(f"Product {self.selected_product_id} updated")
    
    def _on_update_failure(self, error):
        """Handle product update failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to update product: {error}")
        logger.error(f"Error updating product: {error}")
    
    def delete_product(self):
        """Delete selected product."""
        if not self.selected_product_id:
            QMessageBox.warning(self, "Warning", "Please select a product first")
            return
        
        reply = QMessageBox.question(self, "Confirm", "Delete this product?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._show_processing(True)
        
        self.delete_worker = DeleteProductWorker(self.selected_product_id)
        self.delete_worker.success.connect(self._on_delete_success, Qt.ConnectionType.QueuedConnection)
        self.delete_worker.failure.connect(self._on_delete_failure, Qt.ConnectionType.QueuedConnection)
        self.delete_worker.start()
    
    def _on_delete_success(self, product_name):
        """Handle successful product deletion."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", f"Product '{product_name}' deleted successfully")
        self._refresh_products()
        self.clear_selection()
        self._populate_categories()
        logger.info(f"Product deleted")
    
    def _on_delete_failure(self, error):
        """Handle product deletion failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to delete product: {error}")
        logger.error(f"Error deleting product: {error}")
    
    def add_new_product(self):
        """Add new product."""
        try:
            barcode = self.new_barcode_entry.text().strip()
            name = self.new_name_entry.text().strip()
            category = self.new_category_entry.text().strip()
            demo_price = float(self.new_demo_price_entry.text().strip())
            stock = int(self.new_stock_entry.text().strip())
            threshold = int(self.new_threshold_entry.text().strip())
            real_price_str = self.new_real_price_entry.text().strip()
            real_price = float(real_price_str) if real_price_str else None
            
            if not all([barcode, name, category, demo_price, stock, threshold]):
                QMessageBox.warning(self, "Warning", "All fields except Real Price are required")
                return
            
            if demo_price < 0 or stock < 0 or threshold < 0:
                QMessageBox.critical(self, "Error", "Prices, stock, and threshold cannot be negative")
                return
            
            self._show_processing(True)
            
            self.add_worker = AddProductWorker(
                barcode, name, category, demo_price, real_price, stock, threshold
            )
            self.add_worker.success.connect(self._on_add_success, Qt.ConnectionType.QueuedConnection)
            self.add_worker.failure.connect(self._on_add_failure, Qt.ConnectionType.QueuedConnection)
            self.add_worker.start()
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Invalid input: {e}")
    
    def _on_add_success(self, product_name):
        """Handle successful product addition."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", f"Product '{product_name}' added successfully")
        self.clear_form()
        self._refresh_products()
        self._populate_categories()
        logger.info(f"New product added: {product_name}")
    
    def _on_add_failure(self, error):
        """Handle product addition failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to add product: {error}")
        logger.error(f"Error adding product: {error}")
    
    def clear_form(self):
        """Clear add product form."""
        self.new_barcode_entry.clear()
        self.new_name_entry.clear()
        self.new_category_entry.clear()
        self.new_demo_price_entry.clear()
        self.new_real_price_entry.clear()
        self.new_stock_entry.setText("50")
        self.new_threshold_entry.setText("10")
    
    def _refresh_alerts(self):
        """Refresh inventory alerts display."""
        self._show_processing(True)
        
        self.alert_worker = AlertLoadWorker()
        self.alert_worker.success.connect(self._on_alerts_loaded, Qt.ConnectionType.QueuedConnection)
        self.alert_worker.failure.connect(self._on_alerts_load_failed, Qt.ConnectionType.QueuedConnection)
        self.alert_worker.start()
    
    def _on_alerts_loaded(self, alerts):
        """Handle loaded alerts."""
        self.alerts_table.setRowCount(0)
        
        for alert in alerts:
            product = alert.product
            days_ago = (datetime.utcnow() - alert.triggered_at).days
            
            row = self.alerts_table.rowCount()
            self.alerts_table.insertRow(row)
            self.alerts_table.setItem(row, 0, QTableWidgetItem(product.name))
            self.alerts_table.setItem(row, 1, QTableWidgetItem(product.barcode))
            self.alerts_table.setItem(row, 2, QTableWidgetItem(str(product.stock_qty)))
            self.alerts_table.setItem(row, 3, QTableWidgetItem(str(product.reorder_threshold)))
            self.alerts_table.setItem(row, 4, QTableWidgetItem(alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S")))
            self.alerts_table.setItem(row, 5, QTableWidgetItem(str(days_ago)))
        
        self.alert_count_label.setText(f"Total Unresolved Alerts: {len(alerts)}")
        self._show_processing(False)
    
    def _on_alerts_load_failed(self, error):
        """Handle alerts load failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to load alerts: {error}")
        logger.error(f"Error loading alerts: {error}")
    
    def resolve_alert(self):
        """Resolve selected alert."""
        selected = self.alerts_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select an alert")
            return
        
        row = selected[0].row()
        product_name = self.alerts_table.item(row, 0).text()
        
        reply = QMessageBox.question(self, "Confirm", f"Mark alert for '{product_name}' as resolved?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._show_processing(True)
        
        self.resolve_worker = ResolveAlertWorker(product_name)
        self.resolve_worker.success.connect(self._on_resolve_success, Qt.ConnectionType.QueuedConnection)
        self.resolve_worker.failure.connect(self._on_resolve_failure, Qt.ConnectionType.QueuedConnection)
        self.resolve_worker.start()
    
    def _on_resolve_success(self):
        """Handle successful alert resolution."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", "Alert marked as resolved")
        self._refresh_alerts()
        logger.info("Alert resolved")
    
    def _on_resolve_failure(self, error):
        """Handle alert resolution failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to resolve alert: {error}")
        logger.error(f"Error resolving alert: {error}")
    
    def resolve_all_alerts(self):
        """Resolve all unresolved alerts."""
        reply = QMessageBox.question(self, "Confirm", "Mark ALL unresolved alerts as resolved?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._show_processing(True)
        
        def resolve_all(session):
            alerts = session.query(InventoryAlert).filter_by(is_resolved=False).all()
            for alert in alerts:
                alert.is_resolved = True
            session.commit()
            return len(alerts)
        
        try:
            count = self._run_with_session(resolve_all)
            self._show_processing(False)
            QMessageBox.information(self, "Success", f"Marked {count} alerts as resolved")
            self._refresh_alerts()
            logger.info(f"All {count} alerts marked as resolved")
        except Exception as e:
            self._show_processing(False)
            QMessageBox.critical(self, "Error", f"Failed to resolve alerts: {e}")
            logger.error(f"Error resolving all alerts: {e}")
    
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