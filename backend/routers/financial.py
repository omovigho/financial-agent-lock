"""Financial operations routes."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from auth import get_current_user
from database import get_db
from models import (
    User, Customer, Account, Transaction, Refund,
    TransactionStatusEnum, RefundStatusEnum
)
from policy_engine import PolicyEngine, PolicyDecision
from token_vault import TokenVault
from retry_utils import retry_with_backoff
from cache_utils import semantic_cache

router = APIRouter(prefix="/api/financial", tags=["financial"])


# ============================================================================
# MODELS
# ============================================================================

class CustomerCreate(BaseModel):
    """Create customer request."""
    email: str
    name: str
    metadata: Optional[Dict[str, Any]] = None


class CustomerResponse(BaseModel):
    """Customer response model."""
    id: int
    email: str
    name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    """Create account request."""
    customer_id: Optional[int] = None
    name: str
    account_type: str
    currency: str = "USD"


class AccountResponse(BaseModel):
    """Account response model."""
    id: int
    customer_id: Optional[int]
    name: str
    account_type: str
    currency: str
    balance: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    """Create transaction request."""
    account_id: int
    customer_id: Optional[int] = None
    transaction_type: str  # "debit", "credit", "refund", "purchase", "transfer"
    amount: int  # In cents
    currency: str = "USD"
    reference: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TransactionResponse(BaseModel):
    """Transaction response model."""
    id: int
    account_id: Optional[int]
    customer_id: Optional[int]
    transaction_type: str
    amount: int
    currency: str
    status: str
    reference: str
    description: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class RefundCreate(BaseModel):
    """Create refund request."""
    transaction_id: int
    customer_id: int
    amount: int  # In cents
    reason: str
    description: Optional[str] = None


class RefundResponse(BaseModel):
    """Refund response model."""
    id: int
    transaction_id: int
    customer_id: int
    amount: int
    currency: str
    status: str
    reason: str
    approval_id: Optional[int]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class TransactionAnalysisResponse(BaseModel):
    """Transaction analysis response."""
    total_debit: int
    total_credit: int
    net_balance: int
    transaction_count: int
    currency: str
    date_range: Dict[str, str]
    by_type: Dict[str, int]


# ============================================================================
# CUSTOMER ENDPOINTS
# ============================================================================

@router.post("/customers", response_model=CustomerResponse)
async def create_customer(
    request: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new customer."""
    policy_engine = PolicyEngine(db)

    # Check policy
    decision = policy_engine.evaluate_action(
        user_id=current_user.id,
        action="create_customer",
        system="financial",
        context={"role": current_user.role}
    )

    if decision["decision"] == PolicyDecision.DENY.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision["reason"]
        )

    # Create customer
    customer = Customer(
        email=request.email,
        name=request.name,
        custom_metadata=request.metadata or {}
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    # Log action
    policy_engine.log_action(
        user_id=current_user.id,
        action="create_customer",
        system="financial",
        resource=f"customer:{customer.id}",
        method="POST",
        status="success",
        result={"customer_id": customer.id}
    )

    return customer


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get customer details."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    return customer


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all customers."""
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers


# ============================================================================
# ACCOUNT ENDPOINTS
# ============================================================================

@router.post("/accounts", response_model=AccountResponse)
async def create_account(
    request: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new account."""
    # Validate customer exists if provided
    if request.customer_id:
        customer = db.query(Customer).filter(Customer.id == request.customer_id).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )

    account = Account(
        customer_id=request.customer_id,
        name=request.name,
        account_type=request.account_type,
        currency=request.currency,
        balance=0
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return account


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get account details."""
    account = db.query(Account).filter(Account.id == account_id).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    return account


@router.get("/customers/{customer_id}/accounts", response_model=List[AccountResponse])
async def list_customer_accounts(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all accounts for a customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    accounts = db.query(Account).filter(Account.customer_id == customer_id).all()
    return accounts


# ============================================================================
# TRANSACTION ENDPOINTS
# ============================================================================

@retry_with_backoff(max_retries=3, base_delay=1)
async def _create_transaction_internal(
    db: Session,
    account_id: int,
    customer_id: Optional[int],
    transaction_type: str,
    amount: int,
    currency: str,
    reference: str,
    description: Optional[str],
    metadata: Dict[str, Any],
    created_by_id: int,
):
    """Internal transaction creation with retry support."""
    # Verify account exists
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    # Create transaction
    transaction = Transaction(
        account_id=account_id,
        customer_id=customer_id,
        transaction_type=transaction_type,
        amount=amount,
        currency=currency,
        reference=reference,
        description=description,
        custom_metadata=metadata,
        created_by=created_by_id,
        status=TransactionStatusEnum.COMPLETED.value
    )

    db.add(transaction)

    # Update account balance
    if transaction_type in ["credit", "refund"]:
        account.balance += amount
    elif transaction_type in ["debit", "purchase"]:
        account.balance -= amount

    db.commit()
    db.refresh(transaction)

    return transaction


@router.post("/transactions", response_model=TransactionResponse)
async def create_transaction(
    request: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new transaction."""
    policy_engine = PolicyEngine(db)

    # Evaluate policy
    decision = policy_engine.evaluate_action(
        user_id=current_user.id,
        action="create_transaction",
        system="financial",
        context={
            "amount": request.amount,
            "role": current_user.role
        }
    )

    if decision["decision"] == PolicyDecision.REQUIRE_APPROVAL.value:
        # Create approval request that will be handled separately
        approval_id = policy_engine.create_approval_request(
            user_id=current_user.id,
            action="create_transaction",
            system="financial",
            request_data=request.dict()
        )
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Approval required. Approval ID: {approval_id}"
        )

    elif decision["decision"] == PolicyDecision.DENY.value:
        policy_engine.log_action(
            user_id=current_user.id,
            action="create_transaction",
            system="financial",
            resource=f"account:{request.account_id}",
            method="POST",
            status="blocked",
            reason=decision["reason"]
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision["reason"]
        )

    # Create transaction
    try:
        transaction = await _create_transaction_internal(
            db=db,
            account_id=request.account_id,
            customer_id=request.customer_id,
            transaction_type=request.transaction_type,
            amount=request.amount,
            currency=request.currency,
            reference=request.reference,
            description=request.description,
            metadata=request.metadata or {},
            created_by_id=current_user.id
        )

        # Log success
        policy_engine.log_action(
            user_id=current_user.id,
            action="create_transaction",
            system="financial",
            resource=f"transaction:{transaction.id}",
            method="POST",
            status="success",
            result={"transaction_id": transaction.id}
        )

        return transaction
    except Exception as e:
        policy_engine.log_action(
            user_id=current_user.id,
            action="create_transaction",
            system="financial",
            resource=f"account:{request.account_id}",
            method="POST",
            status="failure",
            reason=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/accounts/{account_id}/transactions", response_model=List[TransactionResponse])
async def list_account_transactions(
    account_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List transactions for an account."""
    account = db.query(Account).filter(Account.id == account_id).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    transactions = db.query(Transaction).filter(
        Transaction.account_id == account_id
    ).offset(skip).limit(limit).all()

    return transactions


@router.get("/accounts/{account_id}/analysis", response_model=TransactionAnalysisResponse)
async def analyze_account_transactions(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze transactions for an account."""
    from cache_utils import semantic_cache
    
    cache_key = f"analysis:account:{account_id}"

    # Check cache
    cached_result = semantic_cache.get(cache_key)
    if cached_result:
        return cached_result

    account = db.query(Account).filter(Account.id == account_id).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    transactions = db.query(Transaction).filter(
        Transaction.account_id == account_id
    ).all()

    # Calculate statistics
    total_debit = sum(t.amount for t in transactions if t.transaction_type in ["debit", "purchase"])
    total_credit = sum(t.amount for t in transactions if t.transaction_type in ["credit", "refund"])
    net_balance = total_credit - total_debit

    by_type = {}
    for t in transactions:
        key = t.transaction_type
        by_type[key] = by_type.get(key, 0) + 1

    result = TransactionAnalysisResponse(
        total_debit=total_debit,
        total_credit=total_credit,
        net_balance=net_balance,
        transaction_count=len(transactions),
        currency=account.currency,
        date_range={
            "start": transactions[0].created_at.isoformat() if transactions else None,
            "end": transactions[-1].created_at.isoformat() if transactions else None,
        },
        by_type=by_type
    )

    # Cache result for 5 minutes
    semantic_cache.set(cache_key, result, ttl=300)

    return result


# ============================================================================
# REFUND ENDPOINTS
# ============================================================================

@router.post("/refunds", response_model=RefundResponse)
async def create_refund(
    request: RefundCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a refund request."""
    policy_engine = PolicyEngine(db)

    # Verify transaction exists
    transaction = db.query(Transaction).filter(Transaction.id == request.transaction_id).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    # Evaluate policy
    decision = policy_engine.evaluate_action(
        user_id=current_user.id,
        action="process_refund",
        system="financial",
        context={
            "amount": request.amount,
            "role": current_user.role
        }
    )

    if decision["decision"] == PolicyDecision.REQUIRE_APPROVAL.value:
        # Create approval request
        approval_id = policy_engine.create_approval_request(
            user_id=current_user.id,
            action="process_refund",
            system="financial",
            request_data=request.dict()
        )
        refund = Refund(
            transaction_id=request.transaction_id,
            customer_id=request.customer_id,
            amount=request.amount,
            currency="USD",
            status=RefundStatusEnum.PENDING.value,
            reason=request.reason,
            description=request.description,
            approval_id=approval_id
        )
        db.add(refund)
        db.commit()
        db.refresh(refund)
        return refund

    elif decision["decision"] == PolicyDecision.DENY.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision["reason"]
        )

    # Create refund with immediate processing
    refund = Refund(
        transaction_id=request.transaction_id,
        customer_id=request.customer_id,
        amount=request.amount,
        currency="USD",
        status=RefundStatusEnum.APPROVED.value,
        reason=request.reason,
        description=request.description
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)

    # Log action
    policy_engine.log_action(
        user_id=current_user.id,
        action="process_refund",
        system="financial",
        resource=f"refund:{refund.id}",
        method="POST",
        status="success",
        result={"refund_id": refund.id}
    )

    return refund


@router.get("/refunds/{refund_id}", response_model=RefundResponse)
async def get_refund(
    refund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get refund details."""
    refund = db.query(Refund).filter(Refund.id == refund_id).first()

    if not refund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund not found"
        )

    return refund


@router.get("/customers/{customer_id}/refunds", response_model=List[RefundResponse])
async def list_customer_refunds(
    customer_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List refunds for a customer."""
    refunds = db.query(Refund).filter(
        Refund.customer_id == customer_id
    ).offset(skip).limit(limit).all()

    return refunds


# ============================================================================
# CURRENT USER FINANCIAL INSIGHTS
# ============================================================================

def _build_transaction_scope_query(db: Session, current_user: User):
    """Return a transaction query scoped to the current user role."""
    query = db.query(Transaction)

    if current_user.role == "admin":
        return query

    customer = db.query(Customer).filter(Customer.email == current_user.email).first()
    if customer:
        return query.filter(
            or_(
                Transaction.customer_id == customer.id,
                Transaction.created_by == current_user.id,
            )
        )

    return query.filter(Transaction.created_by == current_user.id)


def _to_transaction_payload(txn: Transaction) -> Dict[str, Any]:
    """Normalize transaction for dashboard rendering."""
    metadata = txn.custom_metadata or {}
    return {
        "id": txn.id,
        "date": txn.created_at.isoformat(),
        "description": txn.description or f"{txn.transaction_type.title()} - {txn.reference}",
        "amount": round((txn.amount or 0) / 100.0, 2),
        "currency": txn.currency,
        "category": metadata.get("category", "Uncategorized"),
        "type": txn.transaction_type,
        "status": txn.status,
        "reference": txn.reference,
    }


@router.get("/my/transactions", response_model=Dict[str, Any])
async def list_my_transactions(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    limit: int = Query(25, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List real transactions for the current user or all users (admin)."""
    query = _build_transaction_scope_query(db, current_user)

    if year is not None:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        query = query.filter(Transaction.created_at >= start, Transaction.created_at < end)

    transactions = query.order_by(Transaction.created_at.desc()).limit(limit).all()

    return {
        "transactions": [_to_transaction_payload(txn) for txn in transactions],
        "count": len(transactions),
        "year": year,
        "scope": "all" if current_user.role == "admin" else "self",
    }


@router.get("/my/summary", response_model=Dict[str, Any])
async def get_my_financial_summary(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return real financial summary metrics for dashboard quick stats."""
    query = _build_transaction_scope_query(db, current_user)

    if year is not None:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        query = query.filter(Transaction.created_at >= start, Transaction.created_at < end)

    transactions = query.order_by(Transaction.created_at.desc()).all()

    inflow_cents = 0
    outflow_cents = 0
    categories: Dict[str, int] = {}

    for txn in transactions:
        amount_cents = abs(txn.amount or 0)
        txn_type = (txn.transaction_type or "").lower()

        if txn_type in {"debit", "purchase"}:
            outflow_cents += amount_cents
        elif txn_type in {"credit", "refund"}:
            inflow_cents += amount_cents
        elif (txn.amount or 0) < 0:
            outflow_cents += amount_cents
        else:
            inflow_cents += amount_cents

        category = (txn.custom_metadata or {}).get("category", "Uncategorized")
        categories[category] = categories.get(category, 0) + 1

    net_cents = inflow_cents - outflow_cents
    top_categories = sorted(categories.items(), key=lambda item: item[1], reverse=True)[:5]

    return {
        "year": year,
        "scope": "all" if current_user.role == "admin" else "self",
        "transaction_count": len(transactions),
        "total_inflow": round(inflow_cents / 100.0, 2),
        "total_outflow": round(outflow_cents / 100.0, 2),
        "net_position": round(net_cents / 100.0, 2),
        "top_categories": [
            {"category": category, "count": count}
            for category, count in top_categories
        ],
    }
