"""Policy API routes."""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from auth import get_current_user
from database import get_db
from models import User, Policy
from policy_engine import PolicyEngine

router = APIRouter(prefix="/api/policy", tags=["policy"])


class PolicyResponse(BaseModel):
    """Policy response model."""
    id: int
    name: str
    action: str
    system: str
    rule: str
    description: Optional[str]
    is_active: bool


@router.get("/list")
async def list_policies(
    system: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all active policies."""
    query = db.query(Policy).filter(Policy.is_active == True)
    
    if system:
        query = query.filter(Policy.system == system)
    
    policies = query.all()
    
    return {
        "policies": [
            {
                "id": p.id,
                "name": p.name,
                "action": p.action,
                "system": p.system,
                "rule": p.rule,
                "description": p.description,
            }
            for p in policies
        ],
        "count": len(policies),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/check")
async def check_action_policy(
    action: str,
    system: str,
    context: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if an action is allowed by policy."""
    policy_engine = PolicyEngine(db)
    
    decision = policy_engine.evaluate_action(
        user_id=current_user.id,
        action=action,
        system=system,
        context=context or {},
    )
    
    return decision


@router.get("/dashboard")
async def policy_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get policy enforcement dashboard data."""
    query = db.query(Policy).filter(Policy.is_active == True)
    policies = query.all()
    
    # Group by system
    by_system = {}
    for policy in policies:
        if policy.system not in by_system:
            by_system[policy.system] = []
        by_system[policy.system].append({
            "name": policy.name,
            "action": policy.action,
            "rule": policy.rule,
            "description": policy.description,
        })
    
    return {
        "policies_by_system": by_system,
        "total_policies": len(policies),
        "systems": list(by_system.keys()),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/demo")
async def policy_demo_data():
    """Get demo data showing policy examples."""
    return {
        "examples": [
            {
                "system": "financial",
                "action": "read_transactions",
                "rule": "allow",
                "description": "Anyone can read transactions",
            },
            {
                "system": "financial",
                "action": "create_transaction",
                "rule": "require_approval",
                "description": "Transactions over $1000 require approval",
                "threshold": 1000,
            },
            {
                "system": "support",
                "action": "process_refund",
                "rule": "require_approval",
                "description": "Refunds over $100 require approval",
                "threshold": 100,
            },
            {
                "system": "erp",
                "action": "create_purchase_order",
                "rule": "require_approval",
                "description": "Orders over $5000 require approval",
                "threshold": 5000,
            },
        ]
    }
