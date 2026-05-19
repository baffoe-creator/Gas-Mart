# ui/admin_panel.py
"""
Admin panel for administrators.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QTabWidget, QComboBox, QProgressBar, QMessageBox,
    QHeaderView, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from data.database import get_session, User, AuditLog
from logic.auth import AuthService
from logic.pricing import PricingContext
from logger import logger


class UserLoadWorker(QThread):
    """Worker thread for loading users."""
    success = pyqtSignal(list)
    failure = pyqtSignal(str)
    
    def run(self):
        session = None
        try:
            session = get_session()
            users = session.query(User).all()
            session.commit()
            self.success.emit(users)
        except Exception as e:
            logger.error(f"User load error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class CreateUserWorker(QThread):
    """Worker thread for creating a user."""
    success = pyqtSignal(str)
    failure = pyqtSignal(str)
    
    def __init__(self, username, password, role, admin_user_id):
        super().__init__()
        self.username = username
        self.password = password
        self.role = role
        self.admin_user_id = admin_user_id
    
    def run(self):
        session = None
        try:
            session = get_session()
            AuthService.create_user(self.username, self.password, self.role, self.admin_user_id, session)
            session.commit()
            self.success.emit(self.username)
        except Exception as e:
            logger.error(f"Create user error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class DeactivateUserWorker(QThread):
    """Worker thread for deactivating a user."""
    success = pyqtSignal(str)
    failure = pyqtSignal(str)
    
    def __init__(self, user_id, admin_user_id):
        super().__init__()
        self.user_id = user_id
        self.admin_user_id = admin_user_id
    
    def run(self):
        session = None
        try:
            session = get_session()
            user = session.query(User).filter_by(id=self.user_id).first()
            if not user:
                self.failure.emit("User not found")
                return
            username = user.username
            AuthService.deactivate_user(self.user_id, self.admin_user_id, session)
            session.commit()
            self.success.emit(username)
        except Exception as e:
            logger.error(f"Deactivate user error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class AuditLogLoadWorker(QThread):
    """Worker thread for loading audit logs."""
    success = pyqtSignal(list)
    failure = pyqtSignal(str)
    
    def run(self):
        session = None
        try:
            session = get_session()
            logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
            session.commit()
            self.success.emit(logs)
        except Exception as e:
            logger.error(f"Audit log load error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class ActivateRealPricesWorker(QThread):
    """Worker thread for activating real prices."""
    success = pyqtSignal()
    failure = pyqtSignal(str)
    
    def __init__(self, admin_user_id):
        super().__init__()
        self.admin_user_id = admin_user_id
    
    def run(self):
        session = None
        try:
            session = get_session()
            PricingContext.activate_real_prices(self.admin_user_id, session)
            session.commit()
            self.success.emit()
        except ValueError as e:
            self.failure.emit(str(e))
        except Exception as e:
            logger.error(f"Activate real prices error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class ActivateDemoPricesWorker(QThread):
    """Worker thread for activating demo prices."""
    success = pyqtSignal()
    failure = pyqtSignal(str)
    
    def __init__(self, admin_user_id):
        super().__init__()
        self.admin_user_id = admin_user_id
    
    def run(self):
        session = None
        try:
            session = get_session()
            PricingContext.activate_demo_prices(self.admin_user_id, session)
            session.commit()
            self.success.emit()
        except Exception as e:
            logger.error(f"Activate demo prices error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class AddUserDialog(QDialog):
    """Dialog for adding a new user."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New User")
        self.setModal(True)
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        form_layout = QGridLayout()
        
        form_layout.addWidget(QLabel("Username:"), 0, 0)
        self.username_entry = QLineEdit()
        form_layout.addWidget(self.username_entry, 0, 1)
        
        form_layout.addWidget(QLabel("Password:"), 1, 0)
        self.password_entry = QLineEdit()
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(self.password_entry, 1, 1)
        
        form_layout.addWidget(QLabel("Role:"), 2, 0)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["cashier", "manager", "admin"])
        form_layout.addWidget(self.role_combo, 2, 1)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_user_data(self):
        """Get user data from dialog."""
        return {
            'username': self.username_entry.text().strip(),
            'password': self.password_entry.text(),
            'role': self.role_combo.currentText()
        }


class AdminWindow(QMainWindow):
    """Admin panel for administrators."""
    
    window_closed = pyqtSignal()
    
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        
        self.setWindowTitle(f"Gas Mart - Admin Panel ({user.username})")
        self.setMinimumSize(1200, 700)
        
        self._create_widgets()
        self._refresh_users()
        self._refresh_audit_log()
        self._load_current_price_mode()
        
        logger.info(f"Admin panel opened for {user.username}")
    
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
        """Create admin panel widgets."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.tab_widget = QTabWidget()
        
        users_tab = QWidget()
        self._create_users_tab(users_tab)
        self.tab_widget.addTab(users_tab, "Users")
        
        price_tab = QWidget()
        self._create_price_tab(price_tab)
        self.tab_widget.addTab(price_tab, "Price Mode")
        
        audit_tab = QWidget()
        self._create_audit_tab(audit_tab)
        self.tab_widget.addTab(audit_tab, "Audit Log")
        
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
    
    def _create_users_tab(self, parent):
        """Create users management tab."""
        layout = QVBoxLayout()
        
        users_frame = QGroupBox("Users List")
        users_layout = QVBoxLayout()
        
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(4)
        self.users_table.setHorizontalHeaderLabels(["Username", "Role", "Active", "Created At"])
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        users_layout.addWidget(self.users_table)
        
        users_frame.setLayout(users_layout)
        layout.addWidget(users_frame)
        
        button_layout = QHBoxLayout()
        
        self.add_user_button = QPushButton("Add User")
        self.add_user_button.clicked.connect(self.add_user)
        button_layout.addWidget(self.add_user_button)
        
        self.deactivate_button = QPushButton("Deactivate Selected")
        self.deactivate_button.clicked.connect(self.deactivate_user)
        button_layout.addWidget(self.deactivate_button)
        
        self.refresh_users_button = QPushButton("Refresh")
        self.refresh_users_button.clicked.connect(self._refresh_users)
        button_layout.addWidget(self.refresh_users_button)
        
        layout.addLayout(button_layout)
        
        parent.setLayout(layout)
    
    def _create_price_tab(self, parent):
        """Create price mode tab."""
        layout = QVBoxLayout()
        
        info_frame = QGroupBox("Current Price Mode")
        info_layout = QVBoxLayout()
        
        self.current_mode_label = QLabel("Loading...")
        self.current_mode_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.current_mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.current_mode_label)
        
        info_frame.setLayout(info_layout)
        layout.addWidget(info_frame)
        
        button_layout = QHBoxLayout()
        
        self.real_prices_button = QPushButton("Activate Real Prices")
        self.real_prices_button.clicked.connect(self.activate_real_prices)
        button_layout.addWidget(self.real_prices_button)
        
        self.demo_prices_button = QPushButton("Revert to Demo Prices")
        self.demo_prices_button.clicked.connect(self.activate_demo_prices)
        button_layout.addWidget(self.demo_prices_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        parent.setLayout(layout)
    
    def _create_audit_tab(self, parent):
        """Create audit log tab."""
        layout = QVBoxLayout()
        
        audit_frame = QGroupBox("Audit Log")
        audit_layout = QVBoxLayout()
        
        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(4)
        self.audit_table.setHorizontalHeaderLabels(["Timestamp", "User", "Action", "Details"])
        self.audit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        audit_layout.addWidget(self.audit_table)
        
        audit_frame.setLayout(audit_layout)
        layout.addWidget(audit_frame)
        
        self.refresh_audit_button = QPushButton("Refresh")
        self.refresh_audit_button.clicked.connect(self._refresh_audit_log)
        layout.addWidget(self.refresh_audit_button)
        
        parent.setLayout(layout)
    
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
    
    def _refresh_users(self):
        """Refresh users list."""
        self._show_processing(True)
        
        self.user_worker = UserLoadWorker()
        self.user_worker.success.connect(self._on_users_loaded, Qt.ConnectionType.QueuedConnection)
        self.user_worker.failure.connect(self._on_users_load_failed, Qt.ConnectionType.QueuedConnection)
        self.user_worker.start()
    
    def _on_users_loaded(self, users):
        """Handle loaded users."""
        self.users_table.setRowCount(0)
        
        for user in users:
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)
            self.users_table.setItem(row, 0, QTableWidgetItem(user.username))
            self.users_table.setItem(row, 1, QTableWidgetItem(user.role))
            self.users_table.setItem(row, 2, QTableWidgetItem("Yes" if user.is_active else "No"))
            self.users_table.setItem(row, 3, QTableWidgetItem(user.created_at.strftime("%Y-%m-%d %H:%M:%S")))
        
        self._show_processing(False)
    
    def _on_users_load_failed(self, error):
        """Handle users load failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to load users: {error}")
        logger.error(f"Error loading users: {error}")
    
    def _refresh_audit_log(self):
        """Refresh audit log."""
        self._show_processing(True)
        
        self.audit_worker = AuditLogLoadWorker()
        self.audit_worker.success.connect(self._on_audit_log_loaded, Qt.ConnectionType.QueuedConnection)
        self.audit_worker.failure.connect(self._on_audit_log_failed, Qt.ConnectionType.QueuedConnection)
        self.audit_worker.start()
    
    def _on_audit_log_loaded(self, logs):
        """Handle loaded audit logs."""
        self.audit_table.setRowCount(0)
        
        for log in logs:
            row = self.audit_table.rowCount()
            self.audit_table.insertRow(row)
            self.audit_table.setItem(row, 0, QTableWidgetItem(log.timestamp.strftime("%Y-%m-%d %H:%M:%S")))
            
            user_name = log.user.username if log.user else "System"
            self.audit_table.setItem(row, 1, QTableWidgetItem(user_name))
            self.audit_table.setItem(row, 2, QTableWidgetItem(log.action))
            
            details = log.details_json[:100] if log.details_json else ""
            self.audit_table.setItem(row, 3, QTableWidgetItem(details))
        
        self._show_processing(False)
    
    def _on_audit_log_failed(self, error):
        """Handle audit log load failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to load audit log: {error}")
        logger.error(f"Error loading audit log: {error}")
    
    def _load_current_price_mode(self):
        """Load and display current price mode."""
        def get_mode(session):
            context = PricingContext(session)
            return context.current_mode.upper()
        
        try:
            mode = self._run_with_session(get_mode)
            self.current_mode_label.setText(mode)
            self.current_mode_label.setStyleSheet(
                "color: #27ae60;" if mode == "REAL" else "color: #e67e22;"
            )
        except Exception as e:
            logger.error(f"Error loading price mode: {e}")
            self.current_mode_label.setText("ERROR")
    
    def add_user(self):
        """Show add user dialog and create user."""
        dialog = AddUserDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            user_data = dialog.get_user_data()
            
            if not user_data['username'] or not user_data['password']:
                QMessageBox.warning(self, "Warning", "Username and password required")
                return
            
            self._show_processing(True)
            
            self.create_user_worker = CreateUserWorker(
                user_data['username'], user_data['password'], user_data['role'], self.user.id
            )
            self.create_user_worker.success.connect(self._on_user_created, Qt.ConnectionType.QueuedConnection)
            self.create_user_worker.failure.connect(self._on_user_create_failed, Qt.ConnectionType.QueuedConnection)
            self.create_user_worker.start()
    
    def _on_user_created(self, username):
        """Handle successful user creation."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", f"User '{username}' created successfully")
        self._refresh_users()
        logger.info(f"User {username} created by admin {self.user.username}")
    
    def _on_user_create_failed(self, error):
        """Handle user creation failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to create user: {error}")
        logger.error(f"Error creating user: {error}")
    
    def deactivate_user(self):
        """Deactivate selected user."""
        selected = self.users_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a user")
            return
        
        row = selected[0].row()
        username = self.users_table.item(row, 0).text()
        
        if username == "admin":
            QMessageBox.critical(self, "Error", "Cannot deactivate admin user")
            return
        
        reply = QMessageBox.question(self, "Confirm", f"Deactivate user '{username}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        def get_user_id(session):
            user = session.query(User).filter_by(username=username).first()
            return user.id if user else None
        
        try:
            user_id = self._run_with_session(get_user_id)
            if not user_id:
                QMessageBox.critical(self, "Error", "User not found")
                return
            
            self._show_processing(True)
            
            self.deactivate_worker = DeactivateUserWorker(user_id, self.user.id)
            self.deactivate_worker.success.connect(self._on_user_deactivated, Qt.ConnectionType.QueuedConnection)
            self.deactivate_worker.failure.connect(self._on_deactivate_failed, Qt.ConnectionType.QueuedConnection)
            self.deactivate_worker.start()
            
        except Exception as e:
            self._show_processing(False)
            QMessageBox.critical(self, "Error", f"Failed to deactivate user: {e}")
    
    def _on_user_deactivated(self, username):
        """Handle successful user deactivation."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", f"User '{username}' deactivated")
        self._refresh_users()
        logger.info(f"User {username} deactivated by admin {self.user.username}")
    
    def _on_deactivate_failed(self, error):
        """Handle deactivation failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to deactivate user: {error}")
        logger.error(f"Error deactivating user: {error}")
    
    def activate_real_prices(self):
        """Activate real pricing."""
        reply = QMessageBox.question(self, "Confirm", 
                                     "Activate real pricing? Ensure all products have real prices set.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._show_processing(True)
        
        self.real_prices_worker = ActivateRealPricesWorker(self.user.id)
        self.real_prices_worker.success.connect(self._on_real_prices_activated, Qt.ConnectionType.QueuedConnection)
        self.real_prices_worker.failure.connect(self._on_price_activation_failed, Qt.ConnectionType.QueuedConnection)
        self.real_prices_worker.start()
    
    def _on_real_prices_activated(self):
        """Handle real prices activation."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", "Real pricing activated")
        self._load_current_price_mode()
        logger.info(f"Real pricing activated by admin {self.user.username}")
    
    def activate_demo_prices(self):
        """Revert to demo pricing."""
        reply = QMessageBox.question(self, "Confirm", "Revert to demo pricing?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._show_processing(True)
        
        self.demo_prices_worker = ActivateDemoPricesWorker(self.user.id)
        self.demo_prices_worker.success.connect(self._on_demo_prices_activated, Qt.ConnectionType.QueuedConnection)
        self.demo_prices_worker.failure.connect(self._on_price_activation_failed, Qt.ConnectionType.QueuedConnection)
        self.demo_prices_worker.start()
    
    def _on_demo_prices_activated(self):
        """Handle demo prices activation."""
        self._show_processing(False)
        QMessageBox.information(self, "Success", "Demo pricing activated")
        self._load_current_price_mode()
        logger.info(f"Demo pricing activated by admin {self.user.username}")
    
    def _on_price_activation_failed(self, error):
        """Handle price activation failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to activate: {error}")
        logger.error(f"Error activating price mode: {error}")
    
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