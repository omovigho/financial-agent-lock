"""Agent API routes."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from auth import get_current_user
from database import get_db
from models import User, Approval, ApprovalStatusEnum
from policy_engine import PolicyEngine, PolicyDecision
from token_vault import TokenVault
from auth0_token_vault import Auth0TokenVaultService
from config import settings
from mcp_tools import tool_registry
from cache_utils import get_cache, CacheKey

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Basic logging for debugging agent flow
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_financial_response(query: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw financial tool output into a structured, user-facing response."""
    if result.get("error"):
        return {
            "status": "failure",
            "message": "I could not retrieve transactions right now. Please try again.",
            "summary": {"error": result.get("error")},
            "timestamp": datetime.utcnow().isoformat(),
        }

    transactions = result.get("transactions") or []
    if not transactions:
        return {
            "status": "success",
            "message": "I checked your account and found no transactions for the selected period.",
            "summary": {
                "transaction_count": 0,
                "total_inflow": 0.0,
                "total_outflow": 0.0,
                "net_position": 0.0,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    query_lower = (query or "").lower().strip()
    wants_breakdown = any(word in query_lower for word in [
        "breakdown", "summary", "financial", "transaction summary", "analysis"
    ])
    wants_spending = any(word in query_lower for word in [
        "spent", "spending", "expense", "cost"
    ])
    wants_balance = any(word in query_lower for word in [
        "balance", "net", "how much do i have", "total balance"
    ])

    total_inflow = 0.0
    total_outflow = 0.0

    for txn in transactions:
        txn_type = (txn.get("type") or txn.get("transaction_type") or "").lower()
        amount = float(txn.get("amount") or 0)
        absolute = abs(amount)

        if txn_type in {"debit", "purchase"}:
            total_outflow += absolute
        elif txn_type in {"credit", "refund"}:
            total_inflow += absolute
        elif amount < 0:
            total_outflow += absolute
        else:
            total_inflow += absolute

    net_position = total_inflow - total_outflow
    summary = {
        "transaction_count": len(transactions),
        "total_inflow": round(total_inflow, 2),
        "total_outflow": round(total_outflow, 2),
        "net_position": round(net_position, 2),
    }

    if wants_breakdown:
        message = (
            "Here is your financial transaction summary:\n"
            f"- Total transactions: {summary['transaction_count']}\n"
            f"- Total inflow: ${summary['total_inflow']:.2f}\n"
            f"- Total outflow: ${summary['total_outflow']:.2f}\n"
            f"- Net position: ${summary['net_position']:.2f}"
        )
    elif wants_balance:
        message = f"Your net position is ${summary['net_position']:.2f}."
    elif wants_spending:
        message = f"You spent ${summary['total_outflow']:.2f} in the selected period."
    else:
        message = (
            f"I found {summary['transaction_count']} transactions with "
            f"${summary['total_inflow']:.2f} inflow and ${summary['total_outflow']:.2f} outflow."
        )

    return {
        "status": "success",
        "message": message,
        "summary": summary,
        "timestamp": datetime.utcnow().isoformat(),
    }


class AgentRequest(BaseModel):
    """Agent request model."""
    query: Optional[str] = None  # Optional - may come from context or action
    system: str  # "financial", "support", "erp"
    action: str  # specific action to perform
    context: Optional[Dict[str, Any]] = None


class TokenRequest(BaseModel):
    """Token request for agent actions."""
    system: str
    scope: str
    ttl_seconds: Optional[int] = None


class AgentExecutionResult(BaseModel):
    """Result of agent execution."""
    status: str
    decision: str
    requirements: Dict[str, Any]
    data: Optional[Dict[str, Any]] = None
    approval_id: Optional[int] = None
    token: Optional[str] = None


@router.post("/execute", response_model=Dict[str, Any])
async def execute_agent_action(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    simple: bool = Query(False, description="If true, return only data.message and data.summary")
):
    """
    Execute an agent action with policy enforcement.
    
    Flow:
    1. Policy engine evaluates action
    2. If allowed or conditionally approved:
       - Request token from vault
       - Execute MCP tool
       - Log action
    3. If denied or requires approval:
       - Create approval request
       - Return with approval_id
    """
    policy_engine = PolicyEngine(db)
    vault = TokenVault(db)

    policy_context = dict(request.context or {})
    if request.query:
        policy_context.setdefault("query", request.query)
    
    # Evaluate policy
    policy_decision = policy_engine.evaluate_action(
        user_id=current_user.id,
        action=request.action,
        system=request.system,
        context=policy_context,
    )
    
    decision = policy_decision["decision"]
    reason = policy_decision["reason"]
    logger.info("policy_decision: %s", policy_decision)
    
    # Handle different policy decisions
    if decision == PolicyDecision.DENY.value:
        policy_engine.log_action(
            user_id=current_user.id,
            action=request.action,
            system=request.system,
            resource=request.context.get("resource", "unknown") if request.context else "unknown",
            method="POST",
            status="blocked",
            reason=reason,
        )
        
        return {
            "status": "blocked",
            "decision": "denied",
            "requirements": {
                "reason": reason,
                "blocked_at": datetime.utcnow().isoformat(),
            }
        }
    
    elif decision == PolicyDecision.REQUIRE_APPROVAL.value:
        # Create approval request
        approval_id = policy_engine.create_approval_request(
            user_id=current_user.id,
            action=request.action,
            system=request.system,
            request_data=request.context or {},
        )
        
        policy_engine.log_action(
            user_id=current_user.id,
            action=request.action,
            system=request.system,
            resource=request.context.get("resource", "unknown") if request.context else "unknown",
            method="POST",
            status="pending_approval",
            reason=reason,
        )
        
        logger.info("approval_required: approval_id=%s", approval_id)
        return {
            "status": "pending",
            "decision": "require_approval",
            "approval_id": approval_id,
            "requirements": {
                "reason": reason,
                "approval_id": approval_id,
                "created_at": datetime.utcnow().isoformat(),
            }
        }
    
    # Policy allows - execute action
    # 1. Request token from vault
    scope = f"read:{request.system}" if "read" in request.action else f"write:{request.system}"
    
    vault_token = vault.create_token(
        user_id=current_user.id,
        scope=scope,
        system=request.system,
    )
    logger.info("vault_token: %s", {"token_id": vault_token.token_id, "scope": vault_token.scope})
    
    # 2. Set database session for tool registry
    tool_registry.set_db(db)
    
        # 3. Execute MCP tool
    try:
        # Add user_id and query to context
        execution_context = request.context or {}
        execution_context["user_id"] = current_user.id
        # include user email for more accurate filtering
        execution_context["user_email"] = current_user.email
        if request.query:
            execution_context["query"] = request.query

        # Optional Auth0 Token Vault exchange for external provider calls.
        token_vault_ctx = execution_context.get("token_vault")
        if settings.auth0_token_vault_enabled and isinstance(token_vault_ctx, dict):
            subject_token = token_vault_ctx.get("subject_token")
            if subject_token:
                connection = (
                    token_vault_ctx.get("connection")
                    or settings.auth0_token_vault_default_connection
                )
                required_scopes = (
                    token_vault_ctx.get("required_scopes")
                    or settings.token_vault_default_scopes_list
                )
                login_hint = token_vault_ctx.get("login_hint")

                provider_token = Auth0TokenVaultService().exchange_access_token(
                    subject_token=subject_token,
                    connection=connection,
                    required_scopes=required_scopes,
                    login_hint=login_hint,
                )

                execution_context["provider_access_token"] = provider_token.get(
                    "access_token"
                )
                execution_context["provider_token_scope"] = provider_token.get("scope")
                execution_context["provider_token_connection"] = connection

        method_name = request.action.replace(f"{request.system}_", "")
        logger.debug("executing tool: system=%s method=%s", request.system, method_name)

        # Special orchestration: detect refund/cancellation intent across systems
        query_text = (request.query or "").lower()
        is_refund_intent = False
        try:
            refund_keywords = ["refund", "failed transaction", "failed", "chargeback", "cancelled", "cancel"]
            ctx_text = str(execution_context.get("context", {})).lower() if execution_context.get("context") else ""
            if any(k in query_text for k in refund_keywords) or any(k in ctx_text for k in refund_keywords):
                is_refund_intent = True
        except Exception:
            is_refund_intent = False

        if is_refund_intent:
            # 1) Check customer's transactions for failed/cancelled entries
            fin_result = tool_registry.execute_tool_method(
                system="financial",
                method="read_transactions",
                token=f"vault_{vault_token.token_id}",
                user_id=current_user.id,
                user_email=current_user.email,
                query=request.query,
            )
            logger.debug("financial check result: %s", fin_result)

            # Normalize and inspect transactions
            transactions = fin_result.get("transactions") if isinstance(fin_result, dict) else None
            failed_txns = []
            if transactions:
                for t in transactions:
                    status = (t.get("status") or "").lower()
                    if status in ("failed", "cancelled", "error", "refunded") or "refund" in (t.get("transaction_type") or ""):
                        failed_txns.append(t)

            if not failed_txns:
                # No failed transactions found — polite informative reply
                message = (
                    "I couldn't find any failed, cancelled, or refunded transactions matching that request for your account. "
                    "If you can provide the transaction ID, date, or billed amount I can look again and advise whether a refund is eligible."
                )
                return {
                    "status": "success",
                    "decision": "executed",
                    "data": {
                        "message": message,
                        "summary": {
                            "checked_transactions": len(transactions) if transactions is not None else 0,
                            "failed_transactions_found": 0,
                        }
                    }
                }

            # Guardrail: do not expose internal policy corpus content to end users.
            combined_message = (
                "I found failed, cancelled, or refunded transactions in your account and can continue the refund workflow. "
                "For security and compliance, internal policy content is not shown in customer responses."
            )

            return {
                "status": "success",
                "decision": "executed",
                "data": {
                    "message": combined_message,
                    "summary": {
                        "failed_transactions_found": len(failed_txns),
                    },
                    "transactions_found": failed_txns,
                }
            }

        # Default: execute the requested tool
        result = tool_registry.execute_tool_method(
            system=request.system,
            method=method_name,
            token=f"vault_{vault_token.token_id}",
            **execution_context
        )
        logger.debug("raw tool result: %s", result)
        
        # Process financial transaction data into natural language
        if request.system == "financial" and request.action == "read_transactions":
            result = process_financial_response(request.query, result)
            logger.debug("processed financial result: %s", result)
            
        
        
        # If client requested a simple view, return only message + summary
        if simple:
            if isinstance(result, dict):
                message = result.get('message')
                summary = result.get('summary')
            else:
                message = None
                summary = None

            return {
                "message": message,
                "summary": summary
            }

        return {
            "status": "success",
            "decision": "executed",
            "token": f"vault_{vault_token.token_id}",
            "requirements": {
                "token_scope": vault_token.scope,
                "expires_at": vault_token.expires_at.isoformat(),
            },
            "data": result,
            "approval_id": None,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        policy_engine.log_action(
            user_id=current_user.id,
            action=request.action,
            system=request.system,
            resource=request.context.get("resource", "unknown") if request.context else "unknown",
            method="POST",
            status="failure",
            reason=str(e),
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tools")
async def list_available_tools(
    current_user: User = Depends(get_current_user),
):
    """List available MCP tools."""
    return {
        "tools": tool_registry.list_tools(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/tokens")
async def list_agent_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's active tokens."""
    vault = TokenVault(db)
    tokens = vault.list_user_tokens(current_user.id)
    
    return {
        "tokens": tokens,
        "count": len(tokens),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/token-request", response_model=Dict[str, Any])
async def request_token(
    request: TokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Request a scoped token for agent use."""
    vault = TokenVault(db)
    
    token = vault.create_token(
        user_id=current_user.id,
        scope=request.scope,
        system=request.system,
        ttl_seconds=request.ttl_seconds,
    )
    
    return {
        "token_id": token.token_id,
        "scope": token.scope,
        "system": token.system,
        "expires_at": token.expires_at.isoformat(),
        "created_at": token.created_at.isoformat(),
    }


@router.post("/session-memory/set")
async def set_session_memory(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Set short-lived session memory for the current user.

    Expected payload: {"session_id": "...", "data": {...}, "ttl": 3600}
    """
    session_id = str(payload.get("session_id", "default"))
    data = payload.get("data", {})
    ttl = int(payload.get("ttl", 3600))

    cache = get_cache()
    key = CacheKey.user_session(current_user.id) + f":{session_id}"
    cache.set(key, data, ttl=ttl)

    return {"status": "ok", "key": key, "ttl": ttl}


@router.get("/session-memory/{session_id}")
async def get_session_memory(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get stored session memory for current user and session id."""
    cache = get_cache()
    key = CacheKey.user_session(current_user.id) + f":{session_id}"
    value = cache.get(key)
    return {"key": key, "value": value}
