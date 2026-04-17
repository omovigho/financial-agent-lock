"""Policy Engine for enforcing access control and security rules."""
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
from sqlalchemy.orm import Session
from models import Policy, AuditLog, User, Approval, ApprovalStatusEnum
import json
import logging


class PolicyDecision(str, Enum):
    """Policy decision outcomes."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyEngine:
    """Central policy enforcement engine."""

    # Routine operational actions should evaluate policy from database rules only.
    NON_RAG_ACTIONS = {
        "read_transactions",
        "get_balance",
        "create_transaction",
        "read_ticket",
        "create_ticket",
        "update_ticket",
        "update_ticket_status",
        "get_ticket",
        "list_tickets",
        "query_tickets",
        "create_purchase_order",
        "read_purchase_orders",
        "check_purchase_order_status",
        "get_inventory",
        "check_low_stock",
    }

    POLICY_INTENT_KEYWORDS = (
        "policy",
        "procedure",
        "guideline",
        "compliance",
        "regulation",
        "rule",
        "approval rule",
        "why denied",
        "why blocked",
        "explain denial",
        "documentation",
    )
    
    def __init__(self, db: Session):
        """Initialize policy engine."""
        self.db = db
        self._initialize_default_policies()

    def _build_policy_intent_text(self, context: Dict[str, Any]) -> str:
        """Build a normalized text blob for intent detection."""
        if not context:
            return ""

        candidate_fields = [
            context.get("query"),
            context.get("message"),
            context.get("reason"),
            context.get("request_summary"),
        ]
        candidate_text = " ".join(str(value) for value in candidate_fields if value)
        return candidate_text.lower().strip()

    def _should_query_rag_for_policy(
        self,
        action: str,
        system: str,
        context: Dict[str, Any],
    ) -> bool:
        """Decide if policy evaluation should call RAG for extra guidance."""
        if context.get("disable_rag_policy_context") is True:
            return False

        if context.get("require_policy_context") is True:
            return True

        normalized_action = (action or "").lower().strip()
        normalized_system = (system or "").lower().strip()
        intent_text = self._build_policy_intent_text(context)

        if any(keyword in intent_text for keyword in self.POLICY_INTENT_KEYWORDS):
            return True

        if normalized_action in self.NON_RAG_ACTIONS:
            return False

        # Keep default behavior cost-efficient: no policy RAG unless explicitly needed.
        if normalized_system in {"financial", "support", "erp"}:
            return False

        return False
    
    def evaluate_action(
        self,
        user_id: int,
        action: str,
        system: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate if an action is allowed by policy.
        
        Args:
            user_id: User requesting action
            action: Action to evaluate (e.g., "read_transactions")
            system: System being accessed (e.g., "financial")
            context: Additional context for policy evaluation
            
        Returns:
            Dict with decision, reason, and requirements
        """
        context = context or {}
        
        # Find matching policy
        policy = self.db.query(Policy).filter(
            Policy.action == action,
            Policy.system == system,
            Policy.is_active == True
        ).first()
        
        if not policy:
            # Default deny if no policy found
            return self._create_decision(
                PolicyDecision.DENY,
                "No policy found for this action"
            )

        rag_result = None
        if self._should_query_rag_for_policy(action=action, system=system, context=context):
            # Optional enrichment: only use RAG when the request asks for policy guidance.
            try:
                from rag_agent.tools.rag_query import rag_query
                logging.info("PolicyEngine: querying RAG corpus for action=%s system=%s", action, system)
                rag_result = rag_query(
                    corpus_name="agent-lock",
                    query=f"policy: {action} {json.dumps(context)}",
                    tool_context=None,
                )
            except Exception as e:
                logging.exception("PolicyEngine: failed to query RAG corpus: %s", e)
        
        # Evaluate policy rule
        if policy.rule == "allow":
            decision = self._create_decision(PolicyDecision.ALLOW, "Policy allows this action")
            if rag_result:
                decision['rag_context'] = rag_result
            return decision
        
        elif policy.rule == "deny":
            decision = self._create_decision(PolicyDecision.DENY, policy.description or "Action denied by policy")
            if rag_result:
                decision['rag_context'] = rag_result
            return decision
        
        elif policy.rule == "require_approval":
            # Check conditional logic
            if self._evaluate_condition(policy.condition, context):
                decision = self._create_decision(
                    PolicyDecision.ALLOW,
                    "Action meets policy conditions"
                )
                if rag_result:
                    decision['rag_context'] = rag_result
                return decision
            else:
                decision = self._create_decision(
                    PolicyDecision.REQUIRE_APPROVAL,
                    f"Action requires approval: {policy.description}",
                    action=action,
                    system=system
                )
                if rag_result:
                    decision['rag_context'] = rag_result
                return decision
        
        return self._create_decision(PolicyDecision.DENY, "Unknown policy rule")
    
    def create_approval_request(
        self,
        user_id: int,
        action: str,
        system: str,
        request_data: Dict[str, Any],
        ttl_minutes: int = 30,
    ) -> int:
        """
        Create an approval request for an action.
        
        Returns:
            Approval request ID
        """
        from datetime import timedelta
        
        approval = Approval(
            user_id=user_id,
            action=action,
            system=system,
            request_data=request_data,
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes)
        )
        self.db.add(approval)
        self.db.commit()
        return approval.id
    
    def resolve_approval(
        self,
        approval_id: int,
        decision: str,  # "approved" or "denied"
        approved_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Resolve an approval request."""
        approval = self.db.query(Approval).filter(Approval.id == approval_id).first()
        if not approval:
            return False
        
        approval.status = decision
        approval.approved_by = approved_by
        approval.reason = reason
        approval.resolved_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def log_action(
        self,
        user_id: int,
        action: str,
        system: str,
        resource: str,
        method: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> int:
        """Log an action for audit trail."""
        log = AuditLog(
            user_id=user_id,
            action=action,
            system=system,
            resource=resource,
            method=method,
            status=status,
            result=result or {},
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log)
        self.db.commit()
        return log.id
    
    def get_audit_logs(
        self,
        user_id: Optional[int] = None,
        system: Optional[str] = None,
        limit: int = 50,
    ) -> list:
        """Retrieve audit logs with optional filtering."""
        query = self.db.query(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if system:
            query = query.filter(AuditLog.system == system)
        
        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
        return [self._format_log(log) for log in logs]
    
    def _create_decision(
        self,
        decision: PolicyDecision,
        reason: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a policy decision response."""
        result = {
            "decision": decision.value,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        result.update(kwargs)
        return result
    
    def _evaluate_condition(
        self,
        condition: Optional[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate conditional logic in policy."""
        if not condition:
            return True
        
        # Simple condition evaluation
        # Example: {"amount": {"operator": "<=", "value": 5000}}
        for field, rule in condition.items():
            if field not in context:
                return False
            
            context_value = context[field]
            operator = rule.get("operator")
            threshold = rule.get("value")
            
            if operator == "<=":
                if not (context_value <= threshold):
                    return False
            elif operator == ">=":
                if not (context_value >= threshold):
                    return False
            elif operator == "<":
                if not (context_value < threshold):
                    return False
            elif operator == ">":
                if not (context_value > threshold):
                    return False
            elif operator == "==":
                if context_value != threshold:
                    return False
        
        return True
    
    def _format_log(self, log: AuditLog) -> Dict[str, Any]:
        """Format audit log for API response."""
        return {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "system": log.system,
            "resource": log.resource,
            "method": log.method,
            "status": log.status,
            "reason": log.reason,
            "result": log.result,
            "created_at": log.created_at.isoformat(),
        }
    
    def _initialize_default_policies(self):
        """Initialize default security policies."""
        default_policies = [
            {
                "name": "readonly_transactions",
                "action": "read_transactions",
                "system": "financial",
                "rule": "allow",
                "description": "Allow reading transactions",
            },
            {
                "name": "write_transactions_approval",
                "action": "create_transaction",
                "system": "financial",
                "rule": "require_approval",
                "condition": {"amount": {"operator": ">", "value": 1000}},
                "description": "Transactions over $1000 require approval",
            },
            {
                "name": "refund_approval",
                "action": "process_refund",
                "system": "support",
                "rule": "require_approval",
                "condition": {"amount": {"operator": ">=", "value": 100}},
                "description": "Refunds over $100 require approval",
            },
            {
                "name": "erp_order_approval",
                "action": "create_purchase_order",
                "system": "erp",
                "rule": "require_approval",
                "condition": {"amount": {"operator": ">=", "value": 5000}},
                "description": "Orders over $5000 require approval",
            },
            {
                "name": "support_ticket_read",
                "action": "read_ticket",
                "system": "support",
                "rule": "allow",
                "description": "Allow reading support tickets",
            },
        ]
        
        for policy_data in default_policies:
            existing = self.db.query(Policy).filter(
                Policy.name == policy_data["name"]
            ).first()
            
            if not existing:
                policy = Policy(
                    **policy_data,
                    is_active=True
                )
                self.db.add(policy)
        
        self.db.commit()
