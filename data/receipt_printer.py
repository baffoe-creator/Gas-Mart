import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from data.database import Sale, Receipt
from logger import logger
from config import APP_NAME


class ReceiptPrinter:
    """Generates receipts in various formats."""

    RECEIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "receipts")

    # PDF layout constants (points; 1 pt = 1/72 inch)
    _MARGIN_LEFT  = 50
    _MARGIN_RIGHT = 550   # effective right edge (letter width ~612 pt)
    _COL_QTY      = 370   # right-align qty here
    _COL_PRICE    = 440   # right-align unit price here
    _COL_TOTAL    = 550   # right-align line total here
    # Maximum characters for a product name before it is truncated with "…"
    # At Helvetica 9pt, ~58 chars fit between left margin and qty column.
    _NAME_MAX_CHARS = 40

    def __init__(self):
        """Ensure receipts directory exists."""
        os.makedirs(self.RECEIPT_DIR, exist_ok=True)

    @staticmethod
    def generate_receipt_number(sale_id: int) -> str:
        """Generate receipt number in format RCP-YYYYMMDD-NNNN."""
        now = datetime.utcnow()
        date_str = now.strftime("%Y%m%d")
        seq_str = str(sale_id).zfill(4)
        return f"RCP-{date_str}-{seq_str}"

    def print_text_receipt(self, sale_id: int, session: Session) -> str:
        """Generate receipt as text file. Returns file path."""
        try:
            sale = session.query(Sale).filter_by(id=sale_id).first()
            if not sale:
                raise ValueError(f"Sale {sale_id} not found")

            receipt_no = self.generate_receipt_number(sale_id)
            payment = sale.payments[0] if sale.payments else None

            lines = []
            lines.append("=" * 50)
            lines.append(APP_NAME.center(50))
            lines.append("ACCRA, GHANA".center(50))
            lines.append("=" * 50)
            lines.append("")
            lines.append(f"Receipt No: {receipt_no}")
            lines.append(f"Date/Time: {sale.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Cashier: {sale.cashier.username}")
            lines.append("")
            lines.append("-" * 50)
            lines.append(f"{'Item':<30} {'Qty':>5} {'Price':>7}")
            lines.append("-" * 50)

            for item in sale.sale_items:
                item_name = item.product.name[:30]
                lines.append(
                    f"{item_name:<30} {item.quantity:>5} {item.unit_price_ghs:>7.2f}"
                )
                lines.append(f"{'':30} {'':>5} Line: {item.line_total_ghs:>6.2f}")

            lines.append("-" * 50)
            lines.append(f"Subtotal: {sale.subtotal:>39.2f} GHS")
            if sale.discount > 0:
                lines.append(f"Discount: {sale.discount:>39.2f} GHS")
            lines.append(f"TOTAL: {sale.total_ghs:>41.2f} GHS")
            lines.append("-" * 50)

            if payment:
                lines.append(f"Payment Method: {payment.payment_method.upper()}")
                if payment.transaction_ref:
                    lines.append(f"Transaction Ref: {payment.transaction_ref}")

            lines.append("")
            lines.append("Thank you for your purchase!".center(50))
            lines.append("")
            lines.append("=" * 50)

            content = "\n".join(lines)

            filename = f"{receipt_no}.txt"
            filepath = os.path.join(self.RECEIPT_DIR, filename)
            with open(filepath, "w") as f:
                f.write(content)

            logger.info(f"Text receipt generated: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error generating text receipt: {e}")
            raise

    def print_pdf_receipt(self, sale_id: int, session: Session) -> str:
        """Generate receipt as PDF file. Returns file path."""
        try:
            sale = session.query(Sale).filter_by(id=sale_id).first()
            if not sale:
                raise ValueError(f"Sale {sale_id} not found")

            receipt_no = self.generate_receipt_number(sale_id)
            filename = f"{receipt_no}.pdf"
            filepath = os.path.join(self.RECEIPT_DIR, filename)

            c = canvas.Canvas(filepath, pagesize=letter)
            width, height = letter

            L  = self._MARGIN_LEFT
            R  = self._MARGIN_RIGHT
            QC = self._COL_QTY
            PC = self._COL_PRICE
            TC = self._COL_TOTAL

            # ── Header ──────────────────────────────────────────────────
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(width / 2, height - 50, APP_NAME)
            c.setFont("Helvetica", 10)
            c.drawCentredString(width / 2, height - 70, "ACCRA, GHANA")

            # ── Receipt metadata ─────────────────────────────────────────
            c.setFont("Helvetica", 9)
            y = height - 100
            c.drawString(L, y, f"Receipt No: {receipt_no}")
            y -= 15
            c.drawString(L, y, f"Date/Time: {sale.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            y -= 15
            c.drawString(L, y, f"Cashier: {sale.cashier.username}")

            # ── Column headers ───────────────────────────────────────────
            y -= 30
            c.setFont("Helvetica-Bold", 9)
            c.drawString(L, y, "Item")
            c.drawRightString(QC, y, "Qty")
            c.drawRightString(PC, y, "Unit Price")
            c.drawRightString(TC, y, "Total")

            y -= 10
            c.setLineWidth(0.5)
            c.line(L, y, R, y)
            y -= 15

            # ── Line items ───────────────────────────────────────────────
            c.setFont("Helvetica", 9)
            for item in sale.sale_items:
                # Truncate long names so they never reach the Qty column.
                raw_name = item.product.name
                if len(raw_name) > self._NAME_MAX_CHARS:
                    name = raw_name[: self._NAME_MAX_CHARS - 1] + "…"
                else:
                    name = raw_name

                c.drawString(L, y, name)
                c.drawRightString(QC, y, str(item.quantity))
                c.drawRightString(PC, y, f"{item.unit_price_ghs:.2f}")
                c.drawRightString(TC, y, f"{item.line_total_ghs:.2f}")
                y -= 14

                # If we're running out of page space, start a new page.
                if y < 80:
                    c.showPage()
                    c.setFont("Helvetica", 9)
                    y = height - 50

            # ── Totals ───────────────────────────────────────────────────
            y -= 5
            c.line(L, y, R, y)
            y -= 15

            c.setFont("Helvetica", 9)
            c.drawString(L, y, "Subtotal (GHS):")
            c.drawRightString(TC, y, f"{sale.subtotal:.2f}")
            y -= 14

            if sale.discount > 0:
                c.drawString(L, y, "Discount (GHS):")
                c.drawRightString(TC, y, f"{sale.discount:.2f}")
                y -= 14

            c.setFont("Helvetica-Bold", 11)
            c.drawString(L, y, "TOTAL (GHS):")
            c.drawRightString(TC, y, f"{sale.total_ghs:.2f}")
            y -= 20

            # ── Payment info ─────────────────────────────────────────────
            c.setFont("Helvetica", 9)
            if sale.payments and sale.payments[0]:
                payment = sale.payments[0]
                c.drawString(L, y, f"Payment: {payment.payment_method.upper()}")
                y -= 14
                if payment.transaction_ref:
                    c.drawString(L, y, f"Ref: {payment.transaction_ref}")
                    y -= 14

            y -= 10
            c.setFont("Helvetica", 9)
            c.drawCentredString(width / 2, y, "Thank you for your purchase!")

            c.save()
            logger.info(f"PDF receipt generated: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error generating PDF receipt: {e}")
            raise

    def issue_receipt(self, sale_id: int, delivery_method: str, session: Session) -> Receipt:
        """
        Issue a receipt for a sale.
        delivery_method: "print" | "pdf" | "txt"
        Returns: Receipt object
        """
        try:
            receipt_no = self.generate_receipt_number(sale_id)

            if delivery_method in ("print", "pdf"):
                self.print_pdf_receipt(sale_id, session)
            elif delivery_method == "txt":
                self.print_text_receipt(sale_id, session)

            receipt = Receipt(
                sale_id=sale_id,
                receipt_no=receipt_no,
                delivery_method=delivery_method
            )
            session.add(receipt)
            session.commit()

            logger.info(f"Receipt issued: {receipt_no} ({delivery_method})")
            return receipt

        except Exception as e:
            session.rollback()
            logger.error(f"Error issuing receipt: {e}")
            raise