"""SQLAlchemy database models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from database import Base
import enum


class UserRoleEnum(str, enum.Enum):
    """User role enumeration."""
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    auth0_id = Column(String, unique=True, index=True)
    name = Column(String)
    role = Column(String, default=UserRoleEnum.USER)  # "user" or "admin"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tokens = relationship("Token", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    approvals = relationship("Approval", back_populates="user")


class Token(Base):
    """Token reference model (not raw token storage)."""
    __tablename__ = "tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token_id = Column(String, unique=True, index=True)  # Reference to Auth0/Vault token
    scope = Column(String)  # e.g., "read:transactions", "write:refund"
    system = Column(String)  # "financial", "support", "erp"
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="tokens")


class Policy(Base):
    """Policy model for access control."""
    __tablename__ = "policies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    action = Column(String)  # e.g., "read_transactions", "create_refund"
    system = Column(String)  # "financial", "support", "erp"
    rule = Column(String)  # "allow", "deny", "require_approval"
    condition = Column(JSON)  # Conditional logic (e.g., amount threshold)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalStatusEnum(str, enum.Enum):
    """Approval status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class Approval(Base):
    """Approval workflow model."""
    __tablename__ = "approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)  # e.g., "create_refund"
    system = Column(String)  # "financial", "support", "erp"
    request_data = Column(JSON)  # Original request details
    status = Column(String, default=ApprovalStatusEnum.PENDING)
    approved_by = Column(String, nullable=True)  # Admin who approved
    reason = Column(Text, nullable=True)  # Approval reason
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime)  # Auto-expiring approval
    
    # Relationships
    user = relationship("User", back_populates="approvals")


class AuditLog(Base):
    """Audit log for tracking all actions."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)
    system = Column(String)  # "financial", "support", "erp"
    resource = Column(String)  # What was affected
    method = Column(String)  # GET, POST, PUT, DELETE
    status = Column(String)  # "success", "failure", "blocked"
    reason = Column(Text, nullable=True)  # Why blocked if applicable
    result = Column(JSON)  # Action result
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class Session(Base):
    """User session model for context and conversation history."""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)  # Format: "user_{user_id}_{timestamp}"
    user_id = Column(Integer, ForeignKey("users.id"))
    context = Column(JSON, default={})  # Conversation context and agent reasoning
    conversation_history = Column(JSON, default=[])  # Last N interactions
    current_corpus = Column(String, default="agent-lock")  # Current RAG corpus
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Session expiration
    
    # Relationships
    user = relationship("User")


class KnowledgeBaseDocument(Base):
    """Knowledge base document model for admin uploads."""
    __tablename__ = "knowledge_base_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String, unique=True, index=True)  # RAG file ID from corpus
    filename = Column(String)
    file_extension = Column(String)  # e.g., ".pdf", ".docx"
    file_size_bytes = Column(Integer)
    corpus_id = Column(String, default="agent-lock")  # Always agent-lock
    source_uri = Column(String, nullable=True)  # Original upload source
    status = Column(String, default="active")  # "active", "archived", "deleted"
    embedded_at = Column(DateTime, nullable=True)  # When embedded in corpus
    uploaded_by = Column(Integer, ForeignKey("users.id"))  # Admin who uploaded
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    uploaded_by_user = relationship("User")


# ============================================================================
# FINANCIAL DOMAIN MODELS
# ============================================================================

class Customer(Base):
    """Customer model for financial operations."""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    status = Column(String, default="active")  # "active", "inactive", "suspended"
    custom_metadata = Column(JSON, default={})  # Custom fields
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    accounts = relationship("Account", back_populates="customer")
    transactions = relationship("Transaction", back_populates="customer")
    refunds = relationship("Refund", back_populates="customer")
    support_tickets = relationship("SupportTicket", back_populates="customer")


class Account(Base):
    """Financial account model (bank, wallet, etc.)."""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)  # Nullable for system accounts
    name = Column(String)
    account_type = Column(String)  # "bank", "wallet", "credit", "system"
    currency = Column(String, default="USD")
    balance = Column(Integer, default=0)  # In cents to avoid float issues
    status = Column(String, default="active")  # "active", "frozen", "closed"
    custom_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")


class TransactionStatusEnum(str, enum.Enum):
    """Transaction status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    REVERSED = "reversed"


class Transaction(Base):
    """Core transaction model for all financial operations."""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    transaction_type = Column(String)  # "debit", "credit", "refund", "purchase", "transfer"
    amount = Column(Integer)  # In cents
    currency = Column(String, default="USD")
    status = Column(String, default=TransactionStatusEnum.PENDING)
    reference = Column(String, unique=True, index=True)  # External reference ID
    description = Column(Text, nullable=True)
    custom_metadata = Column(JSON, default={})  # Additional context
    approval_id = Column(Integer, ForeignKey("approvals.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    account = relationship("Account", back_populates="transactions")
    customer = relationship("Customer", back_populates="transactions")
    approval = relationship("Approval")
    created_by_user = relationship("User")


class RefundStatusEnum(str, enum.Enum):
    """Refund status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Refund(Base):
    """Refund model for customer refund operations."""
    __tablename__ = "refunds"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    amount = Column(Integer)  # In cents
    currency = Column(String, default="USD")
    status = Column(String, default=RefundStatusEnum.PENDING)
    reason = Column(String)  # "customer_request", "defective_product", "duplicate_charge", etc.
    description = Column(Text, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_id = Column(Integer, ForeignKey("approvals.id"), nullable=True)
    refund_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)  # Resulting refund transaction
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    transaction = relationship("Transaction", foreign_keys=[transaction_id])
    customer = relationship("Customer", back_populates="refunds")
    approved_by_user = relationship("User")
    approval = relationship("Approval")
    refund_transaction = relationship("Transaction", foreign_keys=[refund_transaction_id])


# ============================================================================
# SUPPORT DOMAIN MODELS
# ============================================================================

class TicketStatusEnum(str, enum.Enum):
    """Support ticket status enumeration."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriorityEnum(str, enum.Enum):
    """Support ticket priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SupportTicket(Base):
    """Support ticket model for customer support."""
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String, unique=True, index=True)  # "TKT-001", "TKT-002", etc.
    customer_id = Column(Integer, ForeignKey("customers.id"))
    subject = Column(String)
    description = Column(Text)
    status = Column(String, default=TicketStatusEnum.OPEN)
    priority = Column(String, default=TicketPriorityEnum.MEDIUM)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)  # Support agent
    category = Column(String, nullable=True)  # "billing", "technical", "refund", etc.
    custom_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="support_tickets")
    assigned_agent = relationship("User")
    messages = relationship("Message", back_populates="ticket")


class MessageSenderEnum(str, enum.Enum):
    """Message sender type enumeration."""
    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"


class Message(Base):
    """Message model for support ticket conversations."""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"))
    sender_type = Column(String)  # "customer", "agent", "system"
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Agent/admin
    sender_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)  # Customer
    content = Column(Text)
    is_internal = Column(Boolean, default=False)  # Internal note not visible to customer
    custom_metadata = Column(JSON, default={})  # Attachments, RAG sources, etc.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")
    sender_user = relationship("User")
    sender_customer = relationship("Customer")


# ============================================================================
# ERP DOMAIN MODELS
# ============================================================================

class PurchaseOrderStatusEnum(str, enum.Enum):
    """Purchase order status enumeration."""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class PurchaseOrder(Base):
    """Purchase order model for ERP automation."""
    __tablename__ = "purchase_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True, index=True)  # "PO-001", "PO-002", etc.
    vendor = Column(String)
    amount = Column(Integer)  # In cents
    currency = Column(String, default="USD")
    status = Column(String, default=PurchaseOrderStatusEnum.PENDING)
    description = Column(Text, nullable=True)
    requested_by = Column(Integer, ForeignKey("users.id"))
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_id = Column(Integer, ForeignKey("approvals.id"), nullable=True)
    category = Column(String, nullable=True)  # "supplies", "equipment", "software", etc.
    custom_metadata = Column(JSON, default={})  # Line items, delivery address, etc.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    requested_by_user = relationship("User", foreign_keys=[requested_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by])
    approval = relationship("Approval")
