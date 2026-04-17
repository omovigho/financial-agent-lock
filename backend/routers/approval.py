"""Approval workflow router for human-in-the-loop system."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as SQLSession

from database import get_db
from models import (
    Approval,
    User,
    ApprovalStatusEnum,
    Transaction,
    TransactionStatusEnum,
    Refund,
    RefundStatusEnum,
)
from routers.auth import get_current_user
from cache_utils import get_cache, CacheKey

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval", tags=["approvals"])


class ApprovalRequest(BaseModel):
    """Approval request creation."""
    action: str
    system: str
    request_data: dict
    reason: Optional[str] = None


class ApprovalAction(BaseModel):
    """Approval action (approve/reject)."""
    decision: str  # "approve" or "reject"
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Approval response model."""
    id: int
    user_id: int
    action: str
    system: str
    request_data: dict
    status: str
    approved_by: Optional[str]
    reason: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]
    expires_at: datetime
    
    class Config:
        from_attributes = True


class ApprovalListResponse(BaseModel):
    """Approval list response."""
    total: int
    pending: int
    approvals: List[ApprovalResponse]


def _coerce_required_int(request_data: Dict[str, Any], key: str) -> int:
    """Parse a required integer field from request_data."""
    value = request_data.get(key)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required approval request_data field: {key}"
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid integer value for request_data field: {key}"
        ) from exc


def _coerce_optional_int(request_data: Dict[str, Any], key: str) -> Optional[int]:
    """Parse an optional integer field from request_data."""
    value = request_data.get(key)
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid integer value for request_data field: {key}"
        ) from exc


def _resolve_refund_transaction(approval: Approval, db: SQLSession) -> Transaction:
    """Resolve target transaction from approval payload (transaction_id or transaction_reference)."""
    request_data = approval.request_data or {}

    transaction_id = _coerce_optional_int(request_data, "transaction_id")
    transaction_reference = request_data.get("transaction_reference")

    if transaction_id is not None:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction {transaction_id} not found"
            )
        return transaction

    if transaction_reference:
        transaction = db.query(Transaction).filter(Transaction.reference == str(transaction_reference)).first()
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with reference {transaction_reference} not found"
            )
        return transaction

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Missing transaction identifier. Provide request_data.transaction_id or request_data.transaction_reference"
    )


def _resolve_refund_amount_cents(
    approval: Approval,
    request_data: Dict[str, Any],
    transaction: Transaction,
) -> int:
    """Normalize approval payload amount into cents across financial/support workflows."""
    raw_amount = request_data.get("amount")
    if raw_amount is None:
        if transaction.amount is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing request_data.amount and transaction has no amount"
            )
        return int(transaction.amount)

    # Support chat approval payload currently stores amount as dollars (e.g., 80.0).
    if approval.system == "support":
        try:
            return int(round(float(raw_amount) * 100))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid numeric amount in support refund approval payload"
            ) from exc

    # Financial API refund payload stores amount in cents.
    try:
        return int(raw_amount)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid integer amount in financial refund approval payload"
        ) from exc


def _finalize_financial_refund_approval(
    approval: Approval,
    db: SQLSession,
    current_user: User,
) -> None:
    """Apply refund side effects when a process_refund approval is approved."""
    request_data = approval.request_data or {}

    transaction = _resolve_refund_transaction(approval=approval, db=db)
    request_customer_id = _coerce_optional_int(request_data, "customer_id")
    amount = _resolve_refund_amount_cents(
        approval=approval,
        request_data=request_data,
        transaction=transaction,
    )
    reason = request_data.get("reason") or "customer_request"
    description = (
        request_data.get("description")
        or request_data.get("request_summary")
        or request_data.get("customer_message")
    )

    if transaction.customer_id and transaction.customer_id != request_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Refund approval customer mismatch: transaction.customer_id "
                f"({transaction.customer_id}) does not match request_data.customer_id "
                f"({request_customer_id})"
            ),
        )

    effective_customer_id = transaction.customer_id or request_customer_id
    if not effective_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot finalize refund without a customer_id"
        )

    current_status = (transaction.status or "").lower()
    allowed_source_statuses = {
        TransactionStatusEnum.FAILED.value,
        TransactionStatusEnum.REFUNDED.value,
    }
    if current_status not in allowed_source_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Transaction must be in failed status before refund approval. "
                f"Current status: {transaction.status}"
            ),
        )

    transaction.status = TransactionStatusEnum.REFUNDED.value
    if not transaction.completed_at:
        transaction.completed_at = datetime.utcnow()

    refund = db.query(Refund).filter(Refund.approval_id == approval.id).order_by(
        Refund.created_at.desc()
    ).first()

    if not refund:
        refund = db.query(Refund).filter(
            Refund.transaction_id == transaction.id,
            Refund.customer_id == effective_customer_id,
            Refund.status == RefundStatusEnum.PENDING.value,
        ).order_by(Refund.created_at.desc()).first()

    resolved_at = datetime.utcnow()

    if refund:
        refund.transaction_id = transaction.id
        refund.customer_id = effective_customer_id
        refund.amount = amount
        refund.currency = transaction.currency or refund.currency or "USD"
        refund.status = RefundStatusEnum.COMPLETED.value
        refund.reason = reason
        if description:
            refund.description = description
        refund.approved_by = current_user.id
        refund.approval_id = approval.id
        refund.resolved_at = resolved_at
    else:
        refund = Refund(
            transaction_id=transaction.id,
            customer_id=effective_customer_id,
            amount=amount,
            currency=transaction.currency or "USD",
            status=RefundStatusEnum.COMPLETED.value,
            reason=reason,
            description=description,
            approved_by=current_user.id,
            approval_id=approval.id,
            resolved_at=resolved_at,
        )
        db.add(refund)


@router.post("/request", response_model=ApprovalResponse)
async def create_approval_request(
    approval_req: ApprovalRequest,
    user_id: int,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalResponse:
    """
    Create an approval request (called by agent/backend).
    
    Args:
        approval_req: Approval request details
        user_id: User requesting the action
        db: Database connection
        current_user: Authenticated user (can be agent service account)
    
    Returns:
        Created approval request
    """
    # Set expiration (e.g., 72 hours from now)
    expires_at = datetime.utcnow() + timedelta(days=3)
    
    # Create approval
    approval = Approval(
        user_id=user_id,
        action=approval_req.action,
        system=approval_req.system,
        request_data=approval_req.request_data,
        status=ApprovalStatusEnum.PENDING,
        reason=approval_req.reason,
        expires_at=expires_at,
    )
    
    db.add(approval)
    db.commit()
    db.refresh(approval)
    
    logger.info(
        f"Approval request {approval.id} created for action '{approval.action}' "
        f"(system: {approval.system}) by user {user_id}"
    )
    
    return ApprovalResponse.from_orm(approval)


@router.get("/queue", response_model=ApprovalListResponse)
async def get_approval_queue(
    status_filter: Optional[str] = None,
    system_filter: Optional[str] = None,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalListResponse:
    """
    Get pending approvals (admin only).
    
    Args:
        status_filter: Filter by status (pending, approved, denied)
        system_filter: Filter by system (financial, support, erp)
        db: Database connection
        current_user: Authenticated user (admin)
    
    Returns:
        List of approvals
    """
    # Check authorization - only admins can view all approvals
    # For now, we'll allow all authenticated users to view their own approvals
    # and let the front-end handle admin-specific filtering
    
    query = db.query(Approval)
    
    # Filter by status
    if status_filter:
        query = query.filter(Approval.status == status_filter)
    else:
        # Default to pending
        query = query.filter(Approval.status == ApprovalStatusEnum.PENDING)
    
    # Filter by system
    if system_filter:
        query = query.filter(Approval.system == system_filter)
    
    # Order by creation time (newest first)
    approvals = query.order_by(Approval.created_at.desc()).all()
    
    pending_count = db.query(Approval).filter(
        Approval.status == ApprovalStatusEnum.PENDING
    ).count()
    
    return ApprovalListResponse(
        total=len(approvals),
        pending=pending_count,
        approvals=[ApprovalResponse.from_orm(a) for a in approvals]
    )


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: int,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalResponse:
    """
    Get approval details.
    
    Args:
        approval_id: Approval ID
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Approval details
    """
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found"
        )
    
    # Check authorization - users can view their own approvals
    if approval.user_id != current_user.id:
        # For now, allow all to view
        # This should be restricted to admin in production
        pass
    
    return ApprovalResponse.from_orm(approval)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: int,
    action: ApprovalAction,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalResponse:
    """
    Approve an approval request.
    
    Args:
        approval_id: Approval ID
        action: Approval action details
        db: Database connection
        current_user: Authenticated user (admin)
    
    Returns:
        Updated approval
    """
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found"
        )
    
    # Check if already resolved
    if approval.status != ApprovalStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval already {approval.status}"
        )
    
    # Check expiration
    if datetime.utcnow() > approval.expires_at:
        approval.status = ApprovalStatusEnum.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request has expired"
        )
    
    # Update approval
    approval.status = ApprovalStatusEnum.APPROVED
    approval.approved_by = current_user.email
    approval.reason = action.reason or "Approved"
    approval.resolved_at = datetime.utcnow()

    # Execute refund mutation as part of the same approval transaction.
    if approval.action == "process_refund" and approval.system in {"financial", "support"}:
        try:
            _finalize_financial_refund_approval(
                approval=approval,
                db=db,
                current_user=current_user,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to finalize approved refund for approval_id=%s", approval.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to finalize refund approval: {str(exc)}"
            ) from exc
    
    db.commit()
    db.refresh(approval)
    
    logger.info(
        f"Approval {approval_id} APPROVED by {current_user.email}. "
        f"Action: {approval.action}, System: {approval.system}"
    )
    
    # Clear cache
    cache = get_cache()
    cache.delete(CacheKey.policy_check(approval.user_id, approval.action))
    
    return ApprovalResponse.from_orm(approval)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: int,
    action: ApprovalAction,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalResponse:
    """
    Reject an approval request.
    
    Args:
        approval_id: Approval ID
        action: Rejection reason
        db: Database connection
        current_user: Authenticated user (admin)
    
    Returns:
        Updated approval
    """
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found"
        )
    
    # Check if already resolved
    if approval.status != ApprovalStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval already {approval.status}"
        )
    
    # Update approval
    approval.status = ApprovalStatusEnum.DENIED
    approval.approved_by = current_user.email
    approval.reason = action.reason or "Rejected"
    approval.resolved_at = datetime.utcnow()
    
    db.commit()
    db.refresh(approval)
    
    logger.info(
        f"Approval {approval_id} REJECTED by {current_user.email}. "
        f"Reason: {approval.reason}"
    )
    
    return ApprovalResponse.from_orm(approval)


@router.get("/user/{user_id}/pending", response_model=List[ApprovalResponse])
async def get_user_pending_approvals(
    user_id: int,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ApprovalResponse]:
    """
    Get pending approvals for a user.
    
    Args:
        user_id: User ID
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        List of pending approvals
    """
    # Check authorization
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view other user's approvals"
        )
    
    approvals = db.query(Approval).filter(
        Approval.user_id == user_id,
        Approval.status == ApprovalStatusEnum.PENDING
    ).order_by(Approval.created_at.desc()).all()
    
    return [ApprovalResponse.from_orm(a) for a in approvals]
