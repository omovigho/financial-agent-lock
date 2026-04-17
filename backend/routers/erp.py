"""ERP operations routes."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

from auth import get_current_user
from database import get_db
from models import User, PurchaseOrder, PurchaseOrderStatusEnum
from policy_engine import PolicyEngine, PolicyDecision
from retry_utils import retry_with_backoff

router = APIRouter(prefix="/api/erp", tags=["erp"])


# ============================================================================
# MODELS
# ============================================================================

class PurchaseOrderCreate(BaseModel):
    """Create purchase order request."""
    vendor: str
    amount: int  # In cents
    currency: str = "USD"
    description: Optional[str] = None
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PurchaseOrderResponse(BaseModel):
    """Purchase order response model."""
    id: int
    po_number: str
    vendor: str
    amount: int
    currency: str
    status: str
    description: Optional[str]
    category: Optional[str]
    requested_by: int
    approved_by: Optional[int]
    approval_id: Optional[int]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class PurchaseOrderUpdate(BaseModel):
    """Update purchase order request."""
    status: Optional[str] = None
    approved_by: Optional[int] = None


# ============================================================================
# PURCHASE ORDER ENDPOINTS
# ============================================================================

@retry_with_backoff(max_retries=3, base_delay=1)
async def _create_purchase_order_internal(
    db: Session,
    vendor: str,
    amount: int,
    currency: str,
    description: Optional[str],
    category: Optional[str],
    metadata: Dict[str, Any],
    requested_by_id: int,
):
    """Internal PO creation with retry support."""
    # Generate PO number
    po_count = db.query(PurchaseOrder).count()
    po_number = f"PO-{str(po_count + 1).zfill(6)}"

    po = PurchaseOrder(
        po_number=po_number,
        vendor=vendor,
        amount=amount,
        currency=currency,
        description=description,
        category=category,
        requested_by=requested_by_id,
        status=PurchaseOrderStatusEnum.PENDING.value,
        custom_metadata=metadata or {}
    )

    db.add(po)
    db.commit()
    db.refresh(po)

    return po


@router.post("/purchase-orders", response_model=PurchaseOrderResponse)
async def create_purchase_order(
    request: PurchaseOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new purchase order."""
    policy_engine = PolicyEngine(db)

    # Evaluate policy
    decision = policy_engine.evaluate_action(
        user_id=current_user.id,
        action="create_purchase_order",
        system="erp",
        context={
            "amount": request.amount,
            "role": current_user.role
        }
    )

    if decision["decision"] == PolicyDecision.REQUIRE_APPROVAL.value:
        # Create PO in PENDING status, will require approval
        po = await _create_purchase_order_internal(
            db=db,
            vendor=request.vendor,
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            category=request.category,
            metadata=request.metadata or {},
            requested_by_id=current_user.id
        )

        # Create approval request
        approval_id = policy_engine.create_approval_request(
            user_id=current_user.id,
            action="create_purchase_order",
            system="erp",
            request_data=request.dict()
        )

        # Link approval to PO
        po.approval_id = approval_id
        db.commit()
        db.refresh(po)

        policy_engine.log_action(
            user_id=current_user.id,
            action="create_purchase_order",
            system="erp",
            resource=f"purchase_order:{po.id}",
            method="POST",
            status="approval_pending",
            result={"po_id": po.id, "approval_id": approval_id}
        )

        return po

    elif decision["decision"] == PolicyDecision.DENY.value:
        policy_engine.log_action(
            user_id=current_user.id,
            action="create_purchase_order",
            system="erp",
            resource="unknown",
            method="POST",
            status="blocked",
            reason=decision["reason"]
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision["reason"]
        )

    # Create PO with auto-approval
    po = await _create_purchase_order_internal(
        db=db,
        vendor=request.vendor,
        amount=request.amount,
        currency=request.currency,
        description=request.description,
        category=request.category,
        metadata=request.metadata or {},
        requested_by_id=current_user.id
    )

    po.status = PurchaseOrderStatusEnum.APPROVED.value
    po.approved_by = current_user.id
    db.commit()
    db.refresh(po)

    policy_engine.log_action(
        user_id=current_user.id,
        action="create_purchase_order",
        system="erp",
        resource=f"purchase_order:{po.id}",
        method="POST",
        status="success",
        result={"po_id": po.id, "po_number": po.po_number}
    )

    return po


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get purchase order details."""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )

    return po


@router.get("/purchase-orders", response_model=List[PurchaseOrderResponse])
async def list_purchase_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    vendor: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List purchase orders with optional filtering."""
    query = db.query(PurchaseOrder)

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)
    if vendor:
        query = query.filter(PurchaseOrder.vendor.ilike(f"%{vendor}%"))

    pos = query.offset(skip).limit(limit).all()
    return pos


@router.put("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_id: int,
    request: PurchaseOrderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update purchase order status."""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )

    policy_engine = PolicyEngine(db)

    if request.status:
        # Check policy for status change
        decision = policy_engine.evaluate_action(
            user_id=current_user.id,
            action="update_purchase_order",
            system="erp",
            context={"role": current_user.role}
        )

        if decision["decision"] == PolicyDecision.DENY.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision["reason"]
            )

        po.status = request.status

        if request.status == PurchaseOrderStatusEnum.APPROVED.value:
            po.approved_by = current_user.id
        elif request.status in [
            PurchaseOrderStatusEnum.RECEIVED.value,
            PurchaseOrderStatusEnum.CANCELLED.value
        ]:
            po.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(po)

    # Log action
    policy_engine.log_action(
        user_id=current_user.id,
        action="update_purchase_order",
        system="erp",
        resource=f"purchase_order:{po.id}",
        method="PUT",
        status="success",
        result={"status": po.status}
    )

    return po


@router.get("/purchase-orders/{po_id}/status", response_model=Dict[str, Any])
async def get_purchase_order_status(
    po_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current status of a purchase order."""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )

    return {
        "po_number": po.po_number,
        "status": po.status,
        "created_at": po.created_at.isoformat(),
        "approved_by": po.approved_by,
        "resolved_at": po.resolved_at.isoformat() if po.resolved_at else None
    }


# ============================================================================
# CURRENT USER ERP INSIGHTS
# ============================================================================

def _build_purchase_order_scope_query(db: Session, current_user: User):
    """Return purchase order query scoped to current role."""
    query = db.query(PurchaseOrder)

    if current_user.role == "admin":
        return query

    return query.filter(PurchaseOrder.requested_by == current_user.id)


def _to_purchase_order_payload(po: PurchaseOrder) -> Dict[str, Any]:
    """Normalize purchase order for dashboard rendering."""
    return {
        "id": po.id,
        "po_number": po.po_number,
        "vendor": po.vendor,
        "amount": round((po.amount or 0) / 100.0, 2),
        "currency": po.currency,
        "status": po.status,
        "description": po.description,
        "category": po.category,
        "created_at": po.created_at.isoformat(),
        "resolved_at": po.resolved_at.isoformat() if po.resolved_at else None,
    }


@router.get("/my/purchase-orders", response_model=Dict[str, Any])
async def list_my_purchase_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    limit: int = Query(25, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List real purchase orders for dashboard analytics."""
    query = _build_purchase_order_scope_query(db, current_user)

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)

    if year is not None:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        query = query.filter(PurchaseOrder.created_at >= start, PurchaseOrder.created_at < end)

    orders = query.order_by(PurchaseOrder.created_at.desc()).limit(limit).all()

    return {
        "purchase_orders": [_to_purchase_order_payload(po) for po in orders],
        "count": len(orders),
        "year": year,
        "scope": "all" if current_user.role == "admin" else "self",
    }


@router.get("/my/summary", response_model=Dict[str, Any])
async def get_my_erp_summary(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return real ERP summary metrics for dashboard cards."""
    query = _build_purchase_order_scope_query(db, current_user)

    if year is not None:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        query = query.filter(PurchaseOrder.created_at >= start, PurchaseOrder.created_at < end)

    orders = query.order_by(PurchaseOrder.created_at.desc()).all()

    status_counts: Dict[str, int] = {}
    vendor_set = set()
    total_amount_cents = 0
    approved_amount_cents = 0
    pending_amount_cents = 0

    for po in orders:
        status_key = (po.status or "unknown").lower()
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        vendor_set.add((po.vendor or "").strip().lower())

        amount_cents = po.amount or 0
        total_amount_cents += amount_cents
        if status_key == PurchaseOrderStatusEnum.APPROVED.value:
            approved_amount_cents += amount_cents
        if status_key in {PurchaseOrderStatusEnum.PENDING.value, PurchaseOrderStatusEnum.DRAFT.value}:
            pending_amount_cents += amount_cents

    return {
        "year": year,
        "scope": "all" if current_user.role == "admin" else "self",
        "total_orders": len(orders),
        "total_order_value": round(total_amount_cents / 100.0, 2),
        "approved_order_value": round(approved_amount_cents / 100.0, 2),
        "pending_order_value": round(pending_amount_cents / 100.0, 2),
        "vendor_count": len([v for v in vendor_set if v]),
        "status_counts": status_counts,
    }
