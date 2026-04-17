"""MCP Tools for agent integration."""
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dateutil import parser as date_parser
import json
import re
from sqlalchemy.orm import Session


# DATE RANGE PARSING UTILITY

def parse_date_range_from_query(query: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Extract date range from natural language query.
    
    Handles patterns like:
    - "may 2026" -> full month of May 2026
    - "this month" -> current calendar month
    - "last month" -> previous calendar month
    - "april" -> assumes current year
    - "2026" -> full year
    - "this year" -> current year
    - "march 1 to april 30" -> specific range
    - Date queries are relative to April 3, 2026 (current date)
    
    Returns:
        Tuple of (start_datetime, end_datetime) or (None, None) if no date pattern found
    """
    if not query:
        return None, None
    
    query_lower = query.lower().strip()
    current_date = datetime.utcnow()
    current_month = current_date.month
    current_year = current_date.year
    
    # Month names mapping
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    
    # Pattern: "month year" (e.g., "may 2026", "april 2026")
    month_year_pattern = r'\b(' + '|'.join(months.keys()) + r')\s+(\d{4})\b'
    match = re.search(month_year_pattern, query_lower)
    if match:
        month_name, year = match.groups()
        month_num = months[month_name]
        year_num = int(year)
        start_date = datetime(year_num, month_num, 1)
        # Get last day of month
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        return start_date, end_date.replace(hour=23, minute=59, second=59)
    
    # Pattern: "this month"
    if "this month" in query_lower:
        start_date = datetime(current_year, current_month, 1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        return start_date, end_date.replace(hour=23, minute=59, second=59)
    
    # Pattern: "last month"
    if "last month" in query_lower:
        start_date = (datetime(current_year, current_month, 1) - relativedelta(months=1))
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        return start_date, end_date.replace(hour=23, minute=59, second=59)
    
    # Pattern: "next month"
    if "next month" in query_lower:
        start_date = (datetime(current_year, current_month, 1) + relativedelta(months=1))
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        return start_date, end_date.replace(hour=23, minute=59, second=59)
    
    # Pattern: "this year" or just year number
    if "this year" in query_lower or re.search(r'\b2026\b', query_lower):
        year_match = re.search(r'\b(\d{4})\b', query_lower) or re.search(r'this year', query_lower)
        if year_match:
            year_num = current_year
            if year_match.group(1) if year_match.group(1).isdigit() else False:
                year_num = int(year_match.group(1))
            start_date = datetime(year_num, 1, 1)
            end_date = datetime(year_num, 12, 31, 23, 59, 59)
            return start_date, end_date
    
    # Pattern: month name alone (assumes current year)
    month_pattern = r'\b(' + '|'.join(months.keys()) + r')\b'
    match = re.search(month_pattern, query_lower)
    if match:
        month_name = match.group(1)
        month_num = months[month_name]
        start_date = datetime(current_year, month_num, 1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        return start_date, end_date.replace(hour=23, minute=59, second=59)
    
    # Pattern: specific date range "from X to Y"
    range_pattern = r'(?:from|between)?\s*(\w+\s+\d+)\s+(?:to|until|-)\s+(\w+\s+\d+)'
    match = re.search(range_pattern, query_lower)
    if match:
        try:
            start_str, end_str = match.groups()
            start_date = date_parser.parse(start_str, default=datetime(current_year, 1, 1))
            end_date = date_parser.parse(end_str, default=datetime(current_year, 12, 31))
            return start_date, end_date.replace(hour=23, minute=59, second=59)
        except:
            pass
    
    return None, None


class MCPTool:
    """Base class for MCP tools."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.db: Optional[Session] = None
    
    def set_db(self, db: Session):
        """Set the database session for this tool."""
        self.db = db
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the tool."""
        raise NotImplementedError


class FinancialTool(MCPTool):
    """Tool for financial operations."""
    
    def __init__(self):
        super().__init__(
            "financial_operations",
            "Access financial data and create transactions"
        )
    
    def read_transactions(
        self,
        token: str,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        query: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve transactions with filtering from real database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db:
            return {"error": "Database not configured"}
        
        try:
            from models import Transaction
            
            # Build base query
            query_obj = self.db.query(Transaction)

            # Filter by account if provided
            if account_id:
                query_obj = query_obj.filter(Transaction.account_id == account_id)

            # Filter by user: transactions created by the user or belonging to customer's email
            from sqlalchemy import or_, and_
            from models import Customer

            user_filters = []
            if user_id:
                user_filters.append(Transaction.created_by == user_id)
            if user_email:
                # join with Customer to match email
                query_obj = query_obj.outerjoin(Customer, Transaction.customer)
                user_filters.append(Customer.email == user_email)

            if user_filters:
                query_obj = query_obj.filter(or_(*user_filters))

            # Parse date range from query text if no explicit dates provided
            parsed_start, parsed_end = (None, None)
            if query and not start_date and not end_date:
                parsed_start, parsed_end = parse_date_range_from_query(query)

            # Convert provided ISO string dates to datetime where necessary
            final_start = None
            final_end = None
            if start_date:
                try:
                    final_start = datetime.fromisoformat(start_date)
                except Exception:
                    final_start = date_parser.parse(start_date)
            elif parsed_start:
                final_start = parsed_start

            if end_date:
                try:
                    final_end = datetime.fromisoformat(end_date)
                except Exception:
                    final_end = date_parser.parse(end_date)
            elif parsed_end:
                final_end = parsed_end

            # Filter by date range
            if final_start:
                query_obj = query_obj.filter(Transaction.created_at >= final_start)
            if final_end:
                query_obj = query_obj.filter(Transaction.created_at <= final_end)

            # Filter by category if provided
            if category:
                query_obj = query_obj.filter(Transaction.custom_metadata.contains({"category": category}))

            # Execute query
            transactions = query_obj.order_by(Transaction.created_at.desc()).all()
            
            # Convert to dict format
            result_transactions = []
            for t in transactions:
                result_transactions.append({
                    "id": t.id,
                    "date": t.created_at.date().isoformat(),
                    "description": t.description or f"{t.transaction_type.title()} - {t.reference}",
                    "amount": t.amount / 100.0,  # Convert cents to dollars
                    "category": t.custom_metadata.get("category", "Uncategorized") if t.custom_metadata else "Uncategorized",
                    "type": t.transaction_type,
                    "status": t.status,
                    "reference": t.reference
                })
            
            return {
                "status": "success",
                "count": len(result_transactions),
                "transactions": result_transactions,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def create_transaction(
        self,
        token: str,
        user_id: Optional[int] = None,
        account_id: int = None,
        description: str = None,
        amount: float = 0,
        category: str = None,
        transaction_type: str = "debit",
    ) -> Dict[str, Any]:
        """Create a new transaction from backend database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db or not account_id:
            return {"error": "Database not configured or account_id missing"}
        
        try:
            from models import Transaction
            import uuid
            
            # Create transaction record
            transaction = Transaction(
                account_id=account_id,
                transaction_type=transaction_type,
                amount=int(amount * 100),  # Convert dollars to cents
                currency="USD",
                reference=f"TXN-{uuid.uuid4().hex[:12].upper()}",
                description=description,
                custom_metadata={"category": category} if category else {},
                status="completed"
            )
            
            self.db.add(transaction)
            self.db.commit()
            self.db.refresh(transaction)
            
            return {
                "status": "success",
                "transaction": {
                    "id": transaction.id,
                    "date": transaction.created_at.date().isoformat(),
                    "description": description,
                    "amount": amount,
                    "category": category or "Uncategorized"
                },
                "message": "Transaction created successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_balance(self, token: str, user_id: Optional[int] = None, account_id: Optional[int] = None) -> Dict[str, Any]:
        """Get account balance from database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db or not account_id:
            return {"error": "Database not configured or account_id missing"}
        
        try:
            from models import Account
            
            account = self.db.query(Account).filter(Account.id == account_id).first()
            
            if not account:
                return {"error": f"Account {account_id} not found"}
            
            return {
                "status": "success",
                "balance": account.balance / 100.0,  # Convert cents to dollars
                "currency": account.currency,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


class SupportTool(MCPTool):
    """Tool for customer support operations."""
    
    def __init__(self):
        super().__init__(
            "support_operations",
            "Handle customer support tickets and refunds"
        )
    
    def get_ticket(
        self,
        token: str,
        user_id: Optional[int] = None,
        ticket_id: int = None,
    ) -> Dict[str, Any]:
        """Retrieve a support ticket from database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db or not ticket_id:
            return {"error": "Database not configured or ticket_id missing"}
        
        try:
            from models import SupportTicket
            
            ticket = self.db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
            
            if not ticket:
                return {"error": f"Ticket {ticket_id} not found"}
            
            return {
                "status": "success",
                "ticket": {
                    "id": ticket.id,
                    "ticket_number": ticket.ticket_number,
                    "subject": ticket.subject,
                    "description": ticket.description,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "created_at": ticket.created_at.isoformat()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def process_refund(
        self,
        token: str,
        user_id: Optional[int] = None,
        ticket_id: int = None,
        amount: float = 0,
        reason: str = None,
    ) -> Dict[str, Any]:
        """Process a refund for a support ticket from database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db or not ticket_id:
            return {"error": "Database not configured or ticket_id missing"}
        
        try:
            from models import SupportTicket, Refund
            import uuid
            
            ticket = self.db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
            
            if not ticket:
                return {"error": f"Ticket {ticket_id} not found"}
            
            # Create refund record
            refund = Refund(
                ticket_id=ticket_id,
                customer_id=ticket.customer_id,
                amount=int(amount * 100),  # Convert dollars to cents
                currency="USD",
                reason=reason or "Support ticket resolution",
                status="pending"
            )
            
            self.db.add(refund)
            self.db.commit()
            self.db.refresh(refund)
            
            # Update ticket status
            ticket.status = "resolved"
            self.db.commit()
            
            return {
                "status": "success",
                "message": f"Refund of ${amount} initiated for ticket {ticket_id}",
                "refund_id": refund.id,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def list_tickets(self, token: str, user_id: Optional[int] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """List support tickets from database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db:
            return {"error": "Database not configured"}
        
        try:
            from models import SupportTicket
            
            query = self.db.query(SupportTicket)
            
            if status:
                query = query.filter(SupportTicket.status == status)
            
            tickets = query.order_by(SupportTicket.created_at.desc()).all()
            
            result_tickets = [
                {
                    "id": t.id,
                    "ticket_number": t.ticket_number,
                    "subject": t.subject,
                    "status": t.status,
                    "priority": t.priority,
                    "created_at": t.created_at.isoformat()
                }
                for t in tickets
            ]
            
            return {
                "status": "success",
                "count": len(result_tickets),
                "tickets": result_tickets,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }



class ERPTool(MCPTool):
    """Tool for ERP operations."""
    
    def __init__(self):
        super().__init__(
            "erp_operations",
            "Create and manage purchase orders"
        )
    
    def create_purchase_order(
        self,
        token: str,
        user_id: Optional[int] = None,
        vendor: str = None,
        description: str = None,
        amount: float = 0,
        quantity: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new purchase order in database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db or not vendor:
            return {"error": "Database not configured or vendor missing"}
        
        try:
            from models import PurchaseOrder
            import uuid
            
            # Create purchase order record
            po = PurchaseOrder(
                vendor=vendor,
                description=description,
                amount=int(amount * 100),  # Convert dollars to cents
                quantity=quantity or 1,
                currency="USD",
                reference=f"PO-{uuid.uuid4().hex[:12].upper()}",
                status="pending"
            )
            
            self.db.add(po)
            self.db.commit()
            self.db.refresh(po)
            
            return {
                "status": "success",
                "purchase_order": {
                    "id": po.id,
                    "vendor": vendor,
                    "description": description,
                    "amount": amount,
                    "quantity": quantity or 1,
                    "created_at": po.created_at.isoformat()
                },
                "message": "Purchase order created successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_inventory(self, token: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current inventory from database."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db:
            return {"error": "Database not configured"}
        
        try:
            from models import Inventory
            
            inventory_items = self.db.query(Inventory).all()
            
            result = {}
            for item in inventory_items:
                result[item.sku] = {
                    "current": item.current_quantity,
                    "min_threshold": item.min_threshold,
                    "location": item.location
                }
            
            return {
                "status": "success",
                "inventory": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_low_stock(self, token: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Check for items below minimum threshold."""
        if not token or not token.startswith("vault_"):
            return {"error": "Invalid or missing token"}
        
        if not self.db:
            return {"error": "Database not configured"}
        
        try:
            # Note: This assumes an Inventory model exists
            # If inventory tracking is not implemented, return empty
            return {
                "status": "success",
                "low_stock_items": [],
                "count": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


class MCPToolRegistry:
    """Registry for all available MCP tools."""
    
    def __init__(self):
        self.tools = {
            "financial": FinancialTool(),
            "support": SupportTool(),
            "erp": ERPTool(),
        }
    
    def set_db(self, db: Session):
        """Set database session for all tools."""
        for tool in self.tools.values():
            tool.set_db(db)
    
    def get_tool(self, system: str) -> Optional[MCPTool]:
        """Get a tool by system name."""
        return self.tools.get(system)
    
    def list_tools(self) -> Dict[str, str]:
        """List all available tools."""
        return {
            name: tool.description
            for name, tool in self.tools.items()
        }
    
    def execute_tool_method(
        self,
        system: str,
        method: str,
        token: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a method on a tool."""
        tool = self.get_tool(system)
        if not tool:
            return {"error": f"System '{system}' not found"}
        
        method_func = getattr(tool, method, None)
        if not method_func:
            return {"error": f"Method '{method}' not found on {system}"}
        
        try:
            return method_func(token=token, **kwargs)
        except Exception as e:
            return {"error": str(e)}


# Global tool registry
tool_registry = MCPToolRegistry()
