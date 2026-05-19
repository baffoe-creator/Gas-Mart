# ui/login_window.py
"""
Login window for Gas Mart application.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from sqlalchemy.orm import make_transient
from data.database import get_session
from logic.auth import AuthService, AuthenticationError
from logger import logger


class LoginWindow(QWidget):
    """Login window UI."""
    
    login_successful = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gas Mart - Login")
        self.setFixedSize(400, 500)
        
        self._create_widgets()
        self._center_window()
    
    def _center_window(self):
        """Center the window on screen."""
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def _create_widgets(self):
        """Create login form widgets."""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title_label = QLabel("GAS MART")
        title_font = QFont("Segoe UI", 22, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50;")
        main_layout.addWidget(title_label)
        main_layout.addSpacing(20)
        
        # Username field
        username_label = QLabel("Username")
        username_label.setFont(QFont("Segoe UI", 10))
        main_layout.addWidget(username_label)
        
        self.username_entry = QLineEdit()
        self.username_entry.setPlaceholderText("Enter username")
        self.username_entry.setMinimumHeight(35)
        self.username_entry.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        main_layout.addWidget(self.username_entry)
        
        # Password field
        password_label = QLabel("Password")
        password_label.setFont(QFont("Segoe UI", 10))
        main_layout.addWidget(password_label)
        
        self.password_entry = QLineEdit()
        self.password_entry.setPlaceholderText("Enter password")
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_entry.setMinimumHeight(35)
        self.password_entry.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        main_layout.addWidget(self.password_entry)
        
        main_layout.addSpacing(10)
        
        # Login button
        self.login_button = QPushButton("LOGIN")
        self.login_button.setMinimumHeight(40)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        self.login_button.clicked.connect(self.login)
        main_layout.addWidget(self.login_button)
        
        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 9pt;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        main_layout.addWidget(self.error_label)
        
        main_layout.addStretch()
        
        # Set layout
        container = QFrame()
        container.setLayout(main_layout)
        
        layout = QVBoxLayout()
        layout.addWidget(container)
        self.setLayout(layout)
        
        # Set focus to username field
        self.username_entry.setFocus()
        
        # Connect Enter key presses
        self.username_entry.returnPressed.connect(self.login)
        self.password_entry.returnPressed.connect(self.login)
    
    def login(self):
        """Handle login button click."""
        username = self.username_entry.text().strip()
        password = self.password_entry.text()
        
        if not username or not password:
            self.error_label.setText("Username and password required")
            return
        
        # Disable UI during login attempt
        self.login_button.setEnabled(False)
        self.username_entry.setEnabled(False)
        self.password_entry.setEnabled(False)
        self.error_label.setText("")
        
        session = None
        try:
            session = get_session()
            user = AuthService.login(username, password, session)
            
            user_role = user.role
            user_id = user.id
            
            session.expunge(user)
            make_transient(user)
            
            user.role = user_role
            user.id = user_id
            
            logger.info(f"User {username} logged in successfully with role {user.role}")
            
            # Clear password field
            self.password_entry.clear()
            
            # Emit signal with user object
            self.login_successful.emit(user)
            
            # Hide login window (parent will handle dashboard)
            self.parent().hide() if self.parent() else self.hide()
            
        except AuthenticationError as e:
            self.error_label.setText(str(e))
            logger.warning(f"Login failed: {e}")
            # Re-enable UI
            self.login_button.setEnabled(True)
            self.username_entry.setEnabled(True)
            self.password_entry.setEnabled(True)
            self.password_entry.clear()
            self.username_entry.setFocus()
            
        except Exception as e:
            self.error_label.setText("Login error. Please try again.")
            logger.error(f"Unexpected login error: {e}", exc_info=True)
            self.login_button.setEnabled(True)
            self.username_entry.setEnabled(True)
            self.password_entry.setEnabled(True)
            
        finally:
            if session:
                session.close()