"""Audit log API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from auth import get_current_user
from database import get_db
from models import User, AuditLog
from policy_engine import PolicyEngine

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
async def get_audit_logs(
    user_id: Optional[int] = None,
    system: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get audit logs with optional filtering."""
    policy_engine = PolicyEngine(db)
    
    logs = policy_engine.get_audit_logs(
        user_id=user_id,
        system=system,
        limit=limit,
    )
    
    return {
        "logs": logs,
        "count": len(logs),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/logs/summary")
async def get_audit_summary(
    system: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get summary statistics of audit logs."""
    query = db.query(AuditLog)
    
    if system:
        query = query.filter(AuditLog.system == system)
    
    logs = query.all()
    
    # Calculate statistics
    total = len(logs)
    success_count = len([l for l in logs if l.status == 'success'])
    blocked_count = len([l for l in logs if l.status == 'blocked'])
    failure_count = len([l for l in logs if l.status == 'failure'])
    
    return {
        "summary": {
            "total_actions": total,
            "successful": success_count,
            "blocked": blocked_count,
            "failed": failure_count,
            "success_rate": (success_count / total * 100) if total > 0 else 0,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/logs/by-system")
async def get_logs_by_system(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get audit logs grouped by system."""
    logs = db.query(AuditLog).all()
    
    by_system = {}
    for log in logs:
        if log.system not in by_system:
            by_system[log.system] = {
                "total": 0,
                "success": 0,
                "blocked": 0,
                "failure": 0,
            }
        
        by_system[log.system]["total"] += 1
        if log.status == 'success':
            by_system[log.system]["success"] += 1
        elif log.status == 'blocked':
            by_system[log.system]["blocked"] += 1
        elif log.status == 'failure':
            by_system[log.system]["failure"] += 1
    
    return {
        "by_system": by_system,
        "timestamp": datetime.utcnow().isoformat(),
    }
