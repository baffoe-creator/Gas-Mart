"""
Sales and inventory reporting service.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from data.database import Sale, SaleItem, Product, Payment
from logger import logger


class ReportService:
    """Service for generating sales and inventory reports."""
    
    @staticmethod
    def daily_sales_report(date: datetime, session: Session) -> dict:
        """Generate sales report for a specific day."""
        try:
            start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            
            sales = session.query(Sale).filter(
                Sale.created_at >= start,
                Sale.created_at < end,
                Sale.status == "completed"
            ).all()
            
            total_ghs = sum(sale.total_ghs for sale in sales)
            transaction_count = len(sales)
            
            # Payment method breakdown
            payment_breakdown = {}
            for sale in sales:
                for payment in sale.payments:
                    method = payment.payment_method
                    if method not in payment_breakdown:
                        payment_breakdown[method] = 0
                    payment_breakdown[method] += payment.amount_ghs
            
            report = {
                "date": date.strftime("%Y-%m-%d"),
                "total_ghs": round(total_ghs, 2),
                "transaction_count": transaction_count,
                "by_payment_method": payment_breakdown
            }
            
            logger.debug(f"Daily report generated for {date.strftime('%Y-%m-%d')}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            raise
    
    @staticmethod
    def weekly_sales_report(week_start: datetime, session: Session) -> dict:
        """Generate sales report for a week."""
        try:
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7)
            
            sales = session.query(Sale).filter(
                Sale.created_at >= week_start,
                Sale.created_at < week_end,
                Sale.status == "completed"
            ).all()
            
            total_ghs = sum(sale.total_ghs for sale in sales)
            transaction_count = len(sales)
            
            payment_breakdown = {}
            for sale in sales:
                for payment in sale.payments:
                    method = payment.payment_method
                    if method not in payment_breakdown:
                        payment_breakdown[method] = 0
                    payment_breakdown[method] += payment.amount_ghs
            
            report = {
                "week_start": week_start.strftime("%Y-%m-%d"),
                "week_end": (week_end - timedelta(days=1)).strftime("%Y-%m-%d"),
                "total_ghs": round(total_ghs, 2),
                "transaction_count": transaction_count,
                "by_payment_method": payment_breakdown
            }
            
            logger.debug(f"Weekly report generated for week starting {week_start.strftime('%Y-%m-%d')}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            raise
    
    @staticmethod
    def monthly_sales_report(month: int, year: int, session: Session) -> dict:
        """Generate sales report for a month."""
        try:
            start = datetime(year, month, 1, 0, 0, 0)
            if month == 12:
                end = datetime(year + 1, 1, 1, 0, 0, 0)
            else:
                end = datetime(year, month + 1, 1, 0, 0, 0)
            
            sales = session.query(Sale).filter(
                Sale.created_at >= start,
                Sale.created_at < end,
                Sale.status == "completed"
            ).all()
            
            total_ghs = sum(sale.total_ghs for sale in sales)
            transaction_count = len(sales)
            
            payment_breakdown = {}
            for sale in sales:
                for payment in sale.payments:
                    method = payment.payment_method
                    if method not in payment_breakdown:
                        payment_breakdown[method] = 0
                    payment_breakdown[method] += payment.amount_ghs
            
            report = {
                "month": f"{month:02d}",
                "year": str(year),
                "total_ghs": round(total_ghs, 2),
                "transaction_count": transaction_count,
                "by_payment_method": payment_breakdown
            }
            
            logger.debug(f"Monthly report generated for {month:02d}/{year}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating monthly report: {e}")
            raise
    
    @staticmethod
    def top_products_report(start_date: datetime, end_date: datetime, session: Session) -> list:
        """
        Generate top products report by units sold.
        Returns: list of {product_name, units_sold, revenue_ghs}
        """
        try:
            results = session.query(
                Product.name,
                func.sum(SaleItem.quantity).label("units_sold"),
                func.sum(SaleItem.line_total_ghs).label("revenue_ghs")
            ).join(SaleItem).join(Sale).filter(
                Sale.created_at >= start_date,
                Sale.created_at <= end_date,
                Sale.status == "completed"
            ).group_by(Product.name).order_by(
                func.sum(SaleItem.quantity).desc()
            ).all()
            
            top_products = [
                {
                    "product_name": row[0],
                    "units_sold": row[1],
                    "revenue_ghs": round(row[2], 2)
                }
                for row in results
            ]
            
            logger.debug(f"Top products report generated ({len(top_products)} products)")
            return top_products
            
        except Exception as e:
            logger.error(f"Error generating top products report: {e}")
            raise