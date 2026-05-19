# main.py
"""
Main entry point for Gas Mart application.
"""
import sys
import threading
import traceback
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer
from logger import logger
from data.database import init_db, get_session
from data.demo_data_loader import check_and_init
from ui.login_window import LoginWindow


def init_application():
    logger.info("=" * 60)
    logger.info("GAS MART MANAGEMENT SYSTEM - STARTING UP")
    logger.info("=" * 60)

    try:
        init_db()
        logger.info("Database initialized")
        check_and_init()
        logger.info("First-run setup completed")
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise


class MainWindow(QMainWindow):
    """Main application window that hosts the login screen."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gas Mart Management System")
        self.setMinimumSize(400, 500)
        self._active_panel = None
        self.show_login()

    def show_login(self):
        """Show the login window as the central widget."""
        self.login_window = LoginWindow(self)
        self.setCentralWidget(self.login_window)
        self.login_window.login_successful.connect(self.on_login_success)
        self.show()

    def on_login_success(self, user):
        """Open the correct panel based on the user's role."""
        logger.info(f"Routing user '{user.username}' with role '{user.role}'")

        if user.role == "cashier":
            from ui.pos_window import POSWindow
            panel = POSWindow(user, parent=None)

        elif user.role == "manager":
            from ui.inventory_panel import InventoryWindow
            panel = InventoryWindow(user, parent=None)

        elif user.role == "admin":
            from ui.admin_panel import AdminWindow
            panel = AdminWindow(user, parent=None)

        else:
            logger.error(f"Unknown role '{user.role}' — falling back to login")
            return

        self._active_panel = panel
        panel.window_closed.connect(self._on_panel_closed)
        self.hide()
        panel.show()

    def _on_panel_closed(self):
        """Called whenever any role panel closes — return to login."""
        self._active_panel = None
        self.show_login()
        self.show()

    def show(self):
        """Show the main window (called when a panel closes/logs out)."""
        super().show()


def main():
    try:
        init_application()

        app = QApplication(sys.argv)
        app.setApplicationName("Gas Mart Management System")

        window = MainWindow()

        logger.info("Application started successfully")
        sys.exit(app.exec())

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()