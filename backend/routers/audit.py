"""Approval API routes."""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from auth import get_current_user
from database import get_db
from models import User, Approval, ApprovalStatusEnum
from policy_engine import PolicyEngine

router = APIRouter(prefix="/api/approval", tags=["approval"])


class ApprovalResponse(BaseModel):
    """Approval response model."""
    id: int
    action: str
    system: str
    status: str
    created_at: str
    expires_at: str
    request_data: dict


class ApprovalResolution(BaseModel):
    """Resolve approval request."""
    decision: str  # "approved" or "denied"
    reason: Optional[str] = None


@router.get("/pending", response_model=List[ApprovalResponse])
async def get_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get pending approval requests for current user."""
    approvals = db.query(Approval).filter(
        Approval.user_id == current_user.id,
        Approval.status == ApprovalStatusEnum.PENDING.value,
    ).all()
    
    return [
        {
            "id": a.id,
            "action": a.action,
            "system": a.system,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
            "expires_at": a.expires_at.isoformat(),
            "request_data": a.request_data,
        }
        for a in approvals
    ]


@router.get("/{approval_id}")
async def get_approval(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get specific approval request."""
    approval = db.query(Approval).filter(
        Approval.id == approval_id,
        Approval.user_id == current_user.id,
    ).first()
    
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found"
        )
    
    return {
        "id": approval.id,
        "action": approval.action,
        "system": approval.system,
        "status": approval.status,
        "request_data": approval.request_data,
        "created_at": approval.created_at.isoformat(),
        "expires_at": approval.expires_at.isoformat(),
        "approved_by": approval.approved_by,
        "reason": approval.reason,
    }


@router.post("/{approval_id}/resolve")
async def resolve_approval(
    approval_id: int,
    resolution: ApprovalResolution,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Resolve an approval request (approve or deny).
    
    Note: In production, this should be restricted to admin users.
    """
    approval = db.query(Approval).filter(
        Approval.id == approval_id,
    ).first()
    
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found"
        )
    
    # Check if approval is expired
    if approval.expires_at <= datetime.utcnow():
        approval.status = ApprovalStatusEnum.EXPIRED.value
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request has expired"
        )
    
    # Resolve
    policy_engine = PolicyEngine(db)
    policy_engine.resolve_approval(
        approval_id=approval_id,
        decision=resolution.decision.lower(),
        approved_by=current_user.email,
        reason=resolution.reason,
    )
    
    return {
        "id": approval_id,
        "status": resolution.decision.lower(),
        "resolved_at": datetime.utcnow().isoformat(),
        "message": f"Approval {resolution.decision.lower()} successfully",
    }


@router.get("/")
async def list_all_approvals(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all approvals with optional filtering."""
    query = db.query(Approval)
    
    if status_filter:
        query = query.filter(Approval.status == status_filter)
    
    approvals = query.order_by(Approval.created_at.desc()).all()
    
    return {
        "approvals": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "action": a.action,
                "system": a.system,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                "approved_by": a.approved_by,
            }
            for a in approvals
        ],
        "count": len(approvals),
        "timestamp": datetime.utcnow().isoformat(),
    }
