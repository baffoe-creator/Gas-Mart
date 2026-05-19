# ui/reports_panel.py
"""
Reports panel for managers and admins.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QGroupBox,
    QComboBox, QProgressBar, QMessageBox, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDateEdit
from datetime import datetime, timedelta
from data.database import get_session
from logic.reporting import ReportService
from logger import logger


class ReportWorker(QThread):
    """Worker thread for generating reports."""
    success = pyqtSignal(dict)
    failure = pyqtSignal(str)
    
    def __init__(self, report_type, date=None, month=None, year=None, start_date=None, end_date=None):
        super().__init__()
        self.report_type = report_type
        self.date = date
        self.month = month
        self.year = year
        self.start_date = start_date
        self.end_date = end_date
    
    def run(self):
        """Generate report in background thread."""
        session = None
        try:
            session = get_session()
            
            if self.report_type == "daily":
                report = ReportService.daily_sales_report(self.date, session)
            elif self.report_type == "weekly":
                report = ReportService.weekly_sales_report(self.date, session)
            elif self.report_type == "monthly":
                report = ReportService.monthly_sales_report(self.month, self.year, session)
            elif self.report_type == "top_products":
                report = ReportService.top_products_report(self.start_date, self.end_date, session)
            else:
                self.failure.emit(f"Unknown report type: {self.report_type}")
                return
            
            session.commit()
            self.success.emit(report)
            
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            self.failure.emit(str(e))
        finally:
            if session:
                session.close()


class ReportsWindow(QMainWindow):
    """Reports window for managers and admins."""
    
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        
        self.setWindowTitle(f"Gas Mart - Reports ({user.username})")
        self.setMinimumSize(1200, 800)
        
        self._create_widgets()
        logger.info(f"Reports panel opened for {user.username}")
    
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
        """Create reports panel widgets."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Control panel
        control_frame = QGroupBox("Report Controls")
        control_layout = QGridLayout()
        
        # Report type selector
        control_layout.addWidget(QLabel("Report Type:"), 0, 0)
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(["daily", "weekly", "monthly", "top_products"])
        self.report_type_combo.currentTextChanged.connect(self.on_report_type_change)
        control_layout.addWidget(self.report_type_combo, 0, 1)
        
        # Date picker
        control_layout.addWidget(QLabel("Date:"), 0, 2)
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        control_layout.addWidget(self.date_edit, 0, 3)
        
        # Quick date buttons
        button_layout = QHBoxLayout()
        self.today_button = QPushButton("Today")
        self.today_button.clicked.connect(self.set_today)
        button_layout.addWidget(self.today_button)
        
        self.week_ago_button = QPushButton("Week Ago")
        self.week_ago_button.clicked.connect(self.set_week_ago)
        button_layout.addWidget(self.week_ago_button)
        
        self.month_ago_button = QPushButton("Month Ago")
        self.month_ago_button.clicked.connect(self.set_month_ago)
        button_layout.addWidget(self.month_ago_button)
        
        control_layout.addLayout(button_layout, 0, 4)
        
        # Generate button
        self.generate_button = QPushButton("Generate Report")
        self.generate_button.clicked.connect(self.generate_report)
        control_layout.addWidget(self.generate_button, 0, 5)
        
        control_frame.setLayout(control_layout)
        layout.addWidget(control_frame)
        
        # Results frame
        results_frame = QGroupBox("Report Results")
        results_layout = QVBoxLayout()
        
        # Summary metrics
        metrics_frame = QFrame()
        metrics_layout = QHBoxLayout()
        
        self.total_label = self._create_metric_card(metrics_layout, "Total Revenue (GHS)", "0.00")
        self.transactions_label = self._create_metric_card(metrics_layout, "Transactions", "0")
        self.avg_label = self._create_metric_card(metrics_layout, "Average Sale (GHS)", "0.00")
        
        metrics_frame.setLayout(metrics_layout)
        results_layout.addWidget(metrics_frame)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        results_layout.addWidget(self.results_table)
        
        results_frame.setLayout(results_layout)
        layout.addWidget(results_frame)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Logout button
        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        layout.addWidget(self.logout_button)
        
        central_widget.setLayout(layout)
        
        # Generate initial report
        self.generate_report()
    
    def _create_metric_card(self, parent_layout, label, value):
        """Create a metric card."""
        card_frame = QGroupBox(label)
        card_layout = QVBoxLayout()
        
        value_label = QLabel(value)
        value_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("color: #27ae60;")
        card_layout.addWidget(value_label)
        
        card_frame.setLayout(card_layout)
        parent_layout.addWidget(card_frame)
        
        return value_label
    
    def set_today(self):
        """Set date to today."""
        self.date_edit.setDate(QDate.currentDate())
    
    def set_week_ago(self):
        """Set date to one week ago."""
        self.date_edit.setDate(QDate.currentDate().addDays(-7))
    
    def set_month_ago(self):
        """Set date to one month ago."""
        self.date_edit.setDate(QDate.currentDate().addMonths(-1))
    
    def on_report_type_change(self):
        """Handle report type change."""
        # No action needed, just refresh when generate is clicked
        pass
    
    def _show_processing(self, show):
        """Show/hide progress bar."""
        if show:
            self.progress_bar.show()
            self.generate_button.setEnabled(False)
            self.logout_button.setEnabled(False)
            self.report_type_combo.setEnabled(False)
            self.date_edit.setEnabled(False)
            self.today_button.setEnabled(False)
            self.week_ago_button.setEnabled(False)
            self.month_ago_button.setEnabled(False)
        else:
            self.progress_bar.hide()
            self.generate_button.setEnabled(True)
            self.logout_button.setEnabled(True)
            self.report_type_combo.setEnabled(True)
            self.date_edit.setEnabled(True)
            self.today_button.setEnabled(True)
            self.week_ago_button.setEnabled(True)
            self.month_ago_button.setEnabled(True)
    
    def generate_report(self):
        """Generate selected report."""
        report_type = self.report_type_combo.currentText()
        date = self.date_edit.date().toPyDate()
        
        self._show_processing(True)
        
        if report_type == "daily":
            self.report_worker = ReportWorker("daily", date=date)
        elif report_type == "weekly":
            self.report_worker = ReportWorker("weekly", date=date)
        elif report_type == "monthly":
            self.report_worker = ReportWorker("monthly", month=date.month, year=date.year)
        elif report_type == "top_products":
            start_date = date - timedelta(days=30)
            self.report_worker = ReportWorker("top_products", start_date=start_date, end_date=date)
        else:
            self._show_processing(False)
            return
        
        self.report_worker.success.connect(self._on_report_ready, Qt.ConnectionType.QueuedConnection)
        self.report_worker.failure.connect(self._on_report_failed, Qt.ConnectionType.QueuedConnection)
        self.report_worker.start()
    
    def _on_report_ready(self, report):
        """Handle successful report generation."""
        report_type = self.report_type_combo.currentText()
        
        if report_type == "daily":
            self._display_daily_report(report)
        elif report_type == "weekly":
            self._display_weekly_report(report)
        elif report_type == "monthly":
            self._display_monthly_report(report)
        elif report_type == "top_products":
            self._display_top_products_report(report)
        
        self._show_processing(False)
    
    def _display_daily_report(self, report):
        """Display daily sales report."""
        self.results_table.clear()
        
        # Set columns
        self.results_table.setColumnCount(2)
        self.results_table.setHorizontalHeaderLabels(["Payment Method", "Amount (GHS)"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        # Add data
        self.results_table.setRowCount(len(report["by_payment_method"]))
        for i, (method, amount) in enumerate(report["by_payment_method"].items()):
            self.results_table.setItem(i, 0, QTableWidgetItem(method.upper()))
            self.results_table.setItem(i, 1, QTableWidgetItem(f"{amount:.2f}"))
        
        # Update metrics
        self.total_label.setText(f"{report['total_ghs']:.2f}")
        self.transactions_label.setText(str(report['transaction_count']))
        
        avg = report['total_ghs'] / report['transaction_count'] if report['transaction_count'] > 0 else 0
        self.avg_label.setText(f"{avg:.2f}")
    
    def _display_weekly_report(self, report):
        """Display weekly sales report."""
        self._display_daily_report(report)  # Same format
    
    def _display_monthly_report(self, report):
        """Display monthly sales report."""
        self._display_daily_report(report)  # Same format
    
    def _display_top_products_report(self, report):
        """Display top products report."""
        self.results_table.clear()
        
        # Set columns
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Product Name", "Units Sold", "Revenue (GHS)"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        # Add data
        self.results_table.setRowCount(len(report))
        
        total_revenue = 0
        total_units = 0
        
        for i, item in enumerate(report):
            self.results_table.setItem(i, 0, QTableWidgetItem(item["product_name"]))
            self.results_table.setItem(i, 1, QTableWidgetItem(str(item["units_sold"])))
            self.results_table.setItem(i, 2, QTableWidgetItem(f"{item['revenue_ghs']:.2f}"))
            
            total_revenue += item["revenue_ghs"]
            total_units += item["units_sold"]
        
        # Update metrics
        self.total_label.setText(f"{total_revenue:.2f}")
        self.transactions_label.setText(str(total_units))
        self.avg_label.setText(f"{total_revenue/len(report):.2f}" if report else "0.00")
    
    def _on_report_failed(self, error):
        """Handle report generation failure."""
        self._show_processing(False)
        QMessageBox.critical(self, "Error", f"Failed to generate report: {error}")
        logger.error(f"Report generation error: {error}")
    
    def logout(self):
        """Logout user."""
        try:
            from logic.auth import AuthService
            self._run_with_session(lambda s: AuthService.logout(self.user.id, s))
        except Exception as e:
            logger.error(f"Logout error: {e}")
        finally:
            self.close()
            if self.parent():
                self.parent().show()