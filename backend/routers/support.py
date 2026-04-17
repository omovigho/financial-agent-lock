"""Support operations routes."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
import re
import logging

from auth import get_current_user
from database import get_db
from models import (
    User, Customer, SupportTicket, Message, Approval, ApprovalStatusEnum,
    TicketStatusEnum, TicketPriorityEnum, MessageSenderEnum
)
from policy_engine import PolicyEngine
from cache_utils import get_cache, CacheKey
from mcp_tools import tool_registry
from routers.approval import _finalize_financial_refund_approval
try:
    from rag_agent.tools.rag_query import rag_query
except Exception:
    # Optional: rag agent may not be configured in all environments
    def rag_query(corpus_name: str = "", query: str = "", tool_context=None) -> dict:
        return {"status": "error", "message": "rag_query unavailable"}
try:
    from rag_agent.tools.get_corpus_info import get_corpus_info
except Exception:
    def get_corpus_info(corpus_name: str = "", tool_context=None) -> dict:
        return {"status": "error", "message": "get_corpus_info unavailable"}

router = APIRouter(prefix="/api/support", tags=["support"])
logger = logging.getLogger(__name__)

COMPACTION_INTERVAL = 3
COMPACTION_OVERLAP_SIZE = 1
MAX_COMPACTED_SUMMARIES = 10
FINANCIAL_SCOPE_KEYWORDS = (
    "refund",
    "transaction",
    "payment",
    "charge",
    "chargeback",
    "invoice",
    "balance",
    "account",
    "transfer",
    "expense",
    "income",
    "financial",
    "statement",
    "purchase",
    "order",
    "inventory",
    "ticket",
    "support",
)
SMALL_TALK_KEYWORDS = (
    "hello",
    "hi",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "thanks",
    "thank you",
)
POLITE_STANDARD_OPENERS = (
    "Thanks for reaching out.",
    "I appreciate your message.",
    "Thanks for checking in.",
)
POLITE_ESCALATION_OPENERS = (
    "I understand how frustrating this can be.",
    "I hear your concern, and I want to help.",
    "I understand your frustration and appreciate you explaining this.",
)


# ============================================================================
# MODELS
# ============================================================================

class SupportTicketCreate(BaseModel):
    """Create support ticket request."""
    customer_id: int
    subject: str
    description: str
    priority: str = "medium"
    category: Optional[str] = None


class SupportTicketResponse(BaseModel):
    """Support ticket response model."""
    id: int
    ticket_number: str
    customer_id: int
    subject: str
    description: str
    status: str
    priority: str
    assigned_to: Optional[int]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    """Create message request."""
    ticket_id: int
    content: str
    is_internal: bool = False


class MessageResponse(BaseModel):
    """Message response model."""
    id: int
    ticket_id: int
    sender_type: str
    sender_user_id: Optional[int]
    sender_customer_id: Optional[int]
    content: str
    is_internal: bool
    custom_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    """Chat message request model."""
    content: str
    is_internal: bool = False


class ChatModeUpdate(BaseModel):
    """Switch between agent/human mode for a ticket."""
    mode: str  # "agent" or "human"
    note: Optional[str] = None


class ChatApprovalDecision(BaseModel):
    """Approval decision request from support admin chat."""
    decision: str  # "approve" or "reject"
    reason: Optional[str] = None


def _build_approval_lookup(messages: List[Message], db: Session) -> Dict[int, Dict[str, Any]]:
    """Collect approval statuses for messages that contain approval metadata."""
    approval_ids = set()

    for message in messages:
        approval = (message.custom_metadata or {}).get("approval")
        if not isinstance(approval, dict):
            continue

        approval_id = approval.get("approval_id")
        if isinstance(approval_id, int):
            approval_ids.add(approval_id)
            continue

        if isinstance(approval_id, str) and approval_id.isdigit():
            approval_ids.add(int(approval_id))

    if not approval_ids:
        return {}

    rows = db.query(Approval).filter(Approval.id.in_(approval_ids)).all()
    return {
        row.id: {
            "status": row.status,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            "approved_by": row.approved_by,
            "reason": row.reason,
        }
        for row in rows
    }


def _serialize_message(message: Message, approval_lookup: Optional[Dict[int, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Serialize a support message including metadata for UI rendering."""
    metadata = message.custom_metadata or {}
    approval = metadata.get("approval")

    if isinstance(approval, dict) and approval_lookup:
        raw_approval_id = approval.get("approval_id")
        approval_id = raw_approval_id if isinstance(raw_approval_id, int) else None
        if approval_id is None and isinstance(raw_approval_id, str) and raw_approval_id.isdigit():
            approval_id = int(raw_approval_id)

        if approval_id in approval_lookup:
            live_status = approval_lookup[approval_id]
            merged_approval = {**approval, **live_status}
            merged_approval["required"] = live_status.get("status") == ApprovalStatusEnum.PENDING.value
            metadata = {**metadata, "approval": merged_approval}

    return {
        "id": message.id,
        "ticket_id": message.ticket_id,
        "sender_type": message.sender_type,
        "sender_user_id": message.sender_user_id,
        "sender_customer_id": message.sender_customer_id,
        "content": message.content,
        "is_internal": message.is_internal,
        "custom_metadata": metadata,
        "created_at": message.created_at.isoformat(),
    }


def _ensure_customer_for_user(current_user: User, db: Session) -> Customer:
    """Ensure every authenticated user has a linked customer record by email."""
    customer = db.query(Customer).filter(Customer.email == current_user.email).first()
    if customer:
        return customer

    customer = Customer(
        email=current_user.email,
        name=current_user.name or current_user.email.split("@")[0],
        status="active",
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _generate_ticket_number(db: Session) -> str:
    """Generate the next support ticket number."""
    ticket_count = db.query(SupportTicket).count()
    return f"TKT-{str(ticket_count + 1).zfill(6)}"


def _ensure_active_chat_ticket(customer: Customer, db: Session) -> SupportTicket:
    """Find or create a persistent chat ticket for the customer."""
    active_ticket = db.query(SupportTicket).filter(
        SupportTicket.customer_id == customer.id,
        SupportTicket.status.in_([
            TicketStatusEnum.OPEN.value,
            TicketStatusEnum.IN_PROGRESS.value,
            TicketStatusEnum.WAITING_CUSTOMER.value,
        ]),
    ).order_by(SupportTicket.updated_at.desc()).first()

    if active_ticket:
        metadata = active_ticket.custom_metadata or {}
        metadata.setdefault("channel", "support_chat")
        metadata.setdefault("chat_mode", "agent")
        metadata.setdefault("compaction", {
            "compaction_interval": COMPACTION_INTERVAL,
            "overlap_size": COMPACTION_OVERLAP_SIZE,
            "invocation_count": 0,
        })
        active_ticket.custom_metadata = metadata
        db.commit()
        db.refresh(active_ticket)
        return active_ticket

    ticket = SupportTicket(
        ticket_number=_generate_ticket_number(db),
        customer_id=customer.id,
        subject="Live Support Chat",
        description="Persistent customer support chat",
        priority=TicketPriorityEnum.MEDIUM.value,
        category="chat",
        status=TicketStatusEnum.OPEN.value,
        custom_metadata={
            "channel": "support_chat",
            "chat_mode": "agent",
            "compaction": {
                "compaction_interval": COMPACTION_INTERVAL,
                "overlap_size": COMPACTION_OVERLAP_SIZE,
                "invocation_count": 0,
            },
            "interaction_memory": [],
            "compacted_summaries": [],
        },
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def _get_customer_for_ticket(ticket: SupportTicket, db: Session) -> Customer:
    customer = db.query(Customer).filter(Customer.id == ticket.customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _assert_ticket_access(ticket: SupportTicket, current_user: User, db: Session) -> None:
    """Ensure user can access this chat ticket."""
    if _is_admin(current_user):
        return

    customer = _ensure_customer_for_user(current_user, db)
    if ticket.customer_id != customer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this ticket")


def _normalize_message_text(content: str) -> str:
    return (content or "").strip().lower()


def _contains_scope_keyword(content: str, keywords: tuple) -> bool:
    return any(keyword in content for keyword in keywords)


def _is_small_talk_message(content: str) -> bool:
    normalized = _normalize_message_text(content)
    if not normalized:
        return False
    return _contains_scope_keyword(normalized, SMALL_TALK_KEYWORDS)


def _is_financial_scope_query(content: str) -> bool:
    normalized = _normalize_message_text(content)
    if not normalized:
        return False
    return _contains_scope_keyword(normalized, FINANCIAL_SCOPE_KEYWORDS)


def _build_polite_opener(message_content: str, escalation: bool = False) -> str:
    openers = POLITE_ESCALATION_OPENERS if escalation else POLITE_STANDARD_OPENERS
    normalized = _normalize_message_text(message_content)
    if not normalized:
        return openers[0]

    selector = sum(ord(ch) for ch in normalized) % len(openers)
    return openers[selector]


def _prepend_polite_response(message_content: str, response_body: str, escalation: bool = False) -> str:
    opener = _build_polite_opener(message_content, escalation=escalation)
    return f"{opener} {response_body}"


def _extract_year(text: str) -> Optional[str]:
    match = re.search(r"\b(20\d{2})\b", text or "")
    return match.group(1) if match else None


def _has_refund_failure_intent(content: str) -> bool:
    lowered = (content or "").lower()
    keywords = ["refund", "failed transaction", "failed", "chargeback", "cancel", "reimburse"]
    return any(keyword in lowered for keyword in keywords)


def _is_financial_breakdown_intent(content: str) -> bool:
    lowered = (content or "").lower()
    breakdown_keywords = [
        "financial breakdown",
        "breakdown",
        "transaction summary",
        "summary",
        "spending",
        "expenses",
        "income",
        "net",
        "transactions for",
    ]
    return any(keyword in lowered for keyword in breakdown_keywords)


def _classify_transaction_amount(txn: Dict[str, Any]) -> Dict[str, float]:
    """Classify transaction amount into inflow/outflow dollars."""
    txn_type = (txn.get("type") or txn.get("transaction_type") or "").lower()
    amount = float(txn.get("amount") or 0)
    absolute = abs(amount)

    if txn_type in {"debit", "purchase"}:
        return {"inflow": 0.0, "outflow": absolute}
    if txn_type in {"credit", "refund"}:
        return {"inflow": absolute, "outflow": 0.0}
    if amount < 0:
        return {"inflow": 0.0, "outflow": absolute}

    return {"inflow": absolute, "outflow": 0.0}


def _build_financial_breakdown_message(message_content: str, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a structured, customer-facing transaction summary."""
    year_hint = _extract_year(message_content)
    scoped_transactions = transactions

    if year_hint:
        scoped_transactions = [
            txn for txn in transactions
            if str(txn.get("date") or "").startswith(year_hint)
        ]

    if not scoped_transactions:
        period = year_hint or "the selected period"
        return {
            "message": (
                f"I checked your account and did not find any transactions for {period}. "
                "Please confirm the year or share a transaction reference so I can verify again."
            ),
            "metadata": {
                "checked_transactions": True,
                "checked_transaction_count": len(transactions),
                "matched_transaction_count": 0,
                "used_knowledge_base": False,
            },
        }

    total_inflow = 0.0
    total_outflow = 0.0
    category_counts: Dict[str, int] = {}

    for txn in scoped_transactions:
        amounts = _classify_transaction_amount(txn)
        total_inflow += amounts["inflow"]
        total_outflow += amounts["outflow"]

        category = txn.get("category") or "Uncategorized"
        category_counts[category] = category_counts.get(category, 0) + 1

    net = total_inflow - total_outflow
    top_categories = sorted(category_counts.items(), key=lambda item: item[1], reverse=True)[:3]
    categories_line = ", ".join(f"{name} ({count})" for name, count in top_categories) or "None"
    period_label = f"{year_hint} " if year_hint else ""

    message = (
        f"Here is your {period_label}financial transaction summary:\n"
        f"- Total transactions: {len(scoped_transactions)}\n"
        f"- Total inflow: ${total_inflow:.2f}\n"
        f"- Total outflow: ${total_outflow:.2f}\n"
        f"- Net position: ${net:.2f}\n"
        f"- Top categories: {categories_line}"
    )

    return {
        "message": message,
        "metadata": {
            "checked_transactions": True,
            "checked_transaction_count": len(transactions),
            "matched_transaction_count": len(scoped_transactions),
            "used_knowledge_base": False,
            "summary": {
                "transaction_count": len(scoped_transactions),
                "total_inflow": round(total_inflow, 2),
                "total_outflow": round(total_outflow, 2),
                "net_position": round(net, 2),
            },
        },
    }


def _find_matching_failed_transactions(content: str, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return failed/reversed transactions that align with the user claim."""
    lowered = (content or "").lower()
    year_hint = _extract_year(content)
    matched: List[Dict[str, Any]] = []

    for txn in transactions:
        status_value = (txn.get("status") or "").lower()
        reference = (txn.get("reference") or "").lower()
        date_value = str(txn.get("date") or "")

        is_failed = status_value in {"failed", "reversed", "cancelled", "error"}
        if not is_failed:
            continue

        if year_hint and not date_value.startswith(year_hint):
            continue

        if reference and reference in lowered:
            matched.append(txn)
            continue

        matched.append(txn)

    return matched


def _compact_ticket_context(ticket: SupportTicket, user_message: str, agent_message: str) -> None:
    """Compact chat context every N invocations while preserving overlap."""
    metadata = ticket.custom_metadata or {}

    compaction = metadata.get("compaction") or {}
    interval = int(compaction.get("compaction_interval", COMPACTION_INTERVAL))
    overlap = int(compaction.get("overlap_size", COMPACTION_OVERLAP_SIZE))
    invocation_count = int(compaction.get("invocation_count", 0)) + 1

    interaction_memory = metadata.get("interaction_memory") or []
    interaction_memory.append({
        "customer": (user_message or "")[:500],
        "agent": (agent_message or "")[:500],
        "at": datetime.utcnow().isoformat(),
    })

    if invocation_count % interval == 0:
        window_size = interval + overlap
        window = interaction_memory[-window_size:]
        summary_lines = [
            f"C: {turn.get('customer', '')[:120]} | A: {turn.get('agent', '')[:120]}"
            for turn in window
        ]
        compacted_entry = {
            "window_end": invocation_count,
            "summary": " || ".join(summary_lines),
            "created_at": datetime.utcnow().isoformat(),
        }

        compacted_summaries = metadata.get("compacted_summaries") or []
        compacted_summaries.append(compacted_entry)
        metadata["compacted_summaries"] = compacted_summaries[-MAX_COMPACTED_SUMMARIES:]
        interaction_memory = interaction_memory[-overlap:] if overlap > 0 else []
        compaction["last_compacted_at"] = datetime.utcnow().isoformat()

    compaction["compaction_interval"] = interval
    compaction["overlap_size"] = overlap
    compaction["invocation_count"] = invocation_count

    metadata["compaction"] = compaction
    metadata["interaction_memory"] = interaction_memory
    ticket.custom_metadata = metadata


def _write_support_cache_memory(customer_id: int, ticket_id: int, user_message: str, agent_message: str) -> None:
    """Persist short-lived session memory for the active support chat."""
    try:
        cache = get_cache()
        key = f"{CacheKey.user_session(customer_id)}:support:{ticket_id}"
        cache.set(key, {
            "last_customer_message": (user_message or "")[:500],
            "last_agent_message": (agent_message or "")[:500],
            "updated_at": datetime.utcnow().isoformat(),
        }, ttl=3600)
    except Exception:
        # Cache must never block primary chat flow.
        pass


def _build_conversation_summary_list(db: Session) -> List[Dict[str, Any]]:
    """Build admin sidebar data for all customer support conversations."""
    tickets = db.query(SupportTicket).order_by(SupportTicket.updated_at.desc()).all()
    results: List[Dict[str, Any]] = []

    for ticket in tickets:
        customer = db.query(Customer).filter(Customer.id == ticket.customer_id).first()
        if not customer:
            continue

        last_message = db.query(Message).filter(
            Message.ticket_id == ticket.id,
            Message.is_internal == False,
        ).order_by(Message.created_at.desc()).first()

        metadata = ticket.custom_metadata or {}
        results.append({
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "customer_id": customer.id,
            "customer_name": customer.name,
            "customer_email": customer.email,
            "status": ticket.status,
            "priority": ticket.priority,
            "chat_mode": metadata.get("chat_mode", "agent"),
            "last_message": last_message.content if last_message else "",
            "last_message_at": last_message.created_at.isoformat() if last_message else ticket.updated_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
        })

    return results


def _build_ticket_payload(ticket: SupportTicket, customer: Customer) -> Dict[str, Any]:
    metadata = ticket.custom_metadata or {}
    compaction = metadata.get("compaction") or {}

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "category": ticket.category,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
        },
        "chat_mode": metadata.get("chat_mode", "agent"),
        "context_summary": (metadata.get("compacted_summaries") or [])[-1] if metadata.get("compacted_summaries") else None,
        "compaction": {
            "compaction_interval": int(compaction.get("compaction_interval", COMPACTION_INTERVAL)),
            "overlap_size": int(compaction.get("overlap_size", COMPACTION_OVERLAP_SIZE)),
            "invocation_count": int(compaction.get("invocation_count", 0)),
            "last_compacted_at": compaction.get("last_compacted_at"),
        },
        "updated_at": ticket.updated_at.isoformat(),
        "created_at": ticket.created_at.isoformat(),
    }


def _query_knowledge_base(message_content: str, failed_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Query agent-lock only when we have validated evidence or a general KB request."""
    seed = " ".join(
        f"{txn.get('reference', '')} {txn.get('status', '')} {txn.get('description', '')}"
        for txn in failed_matches[:3]
    )
    query_text = f"Customer support response guidance: {message_content}. Verified transactions: {seed}".strip()

    try:
        result = rag_query(corpus_name="agent-lock", query=query_text, tool_context=None)
        if not isinstance(result, dict):
            return {"status": "error", "message": "Unexpected RAG response format"}
        return result
    except Exception as exc:
        return {"status": "error", "message": f"Knowledge base query failed: {str(exc)}"}


def _extract_knowledge_snippets(rag_result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize RAG results into UI-friendly snippets and sources."""
    snippets: List[str] = []
    sources: List[str] = []

    for item in rag_result.get("results", []) if isinstance(rag_result, dict) else []:
        text = item.get("text") or item.get("chunk") or ""
        source = item.get("source_name") or item.get("source_uri") or item.get("file_id")
        if text:
            snippets.append(text[:450])
        if source:
            sources.append(str(source))

    return {
        "snippets": snippets[:3],
        "sources": list(dict.fromkeys(sources))[:3],
    }


def _generate_support_agent_reply(
    ticket: SupportTicket,
    customer: Customer,
    current_user: User,
    message_content: str,
    db: Session,
) -> Dict[str, Any]:
    """Transaction-first support response strategy with conditional approval routing."""
    if not _is_financial_scope_query(message_content):
        if _is_small_talk_message(message_content):
            scoped_prompt = (
                "I can assist with this financial system, including transactions, balances, refunds, "
                "purchase orders, and support ticket updates. Share your financial request and I will check it."
            )
        else:
            scoped_prompt = (
                "I can only help with requests related to this financial system, such as transactions, balances, "
                "refunds, purchase orders, inventory, and support tickets. I cannot assist with unrelated topics, "
                "and I cannot share internal company privacy or policy details."
            )

        return {
            "message": _prepend_polite_response(message_content, scoped_prompt),
            "metadata": {
                "checked_transactions": False,
                "used_knowledge_base": False,
                "guardrail": "financial_scope_only",
            },
        }

    tool_registry.set_db(db)
    tx_result = tool_registry.execute_tool_method(
        system="financial",
        method="read_transactions",
        token="vault_support_chat",
        user_id=current_user.id,
        user_email=customer.email,
        query=message_content,
    )

    if tx_result.get("error"):
        return {
            "message": _prepend_polite_response(
                message_content,
                "I could not read your transaction history right now. "
                "Please retry in a moment, or share your transaction reference so I can escalate quickly.",
            ),
            "metadata": {
                "checked_transactions": False,
                "transaction_error": tx_result.get("error"),
                "used_knowledge_base": False,
            },
        }

    transactions = tx_result.get("transactions") or []
    intent_is_refund = _has_refund_failure_intent(message_content)
    intent_is_breakdown = _is_financial_breakdown_intent(message_content)

    if intent_is_refund:
        matched = _find_matching_failed_transactions(message_content, transactions)

        if not matched:
            return {
                "message": _prepend_polite_response(
                    message_content,
                    "However, I checked your transactions and could not find a failed or cancelled transaction "
                    "matching your request. Please share the transaction ID, amount, or exact date so I can "
                    "verify again and guide the next step.",
                    escalation=True,
                ),
                "metadata": {
                    "checked_transactions": True,
                    "checked_transaction_count": len(transactions),
                    "matched_failed_transactions": 0,
                    "used_knowledge_base": False,
                    "summary": "No eligible failed/cancelled transaction found.",
                },
            }

        policy_engine = PolicyEngine(db)
        first_amount = abs(float(matched[0].get("amount", 0) or 0))
        decision = policy_engine.evaluate_action(
            user_id=current_user.id,
            action="process_refund",
            system="support",
            context={"amount": first_amount, "role": current_user.role},
        )

        approval_payload: Optional[Dict[str, Any]] = None
        if decision.get("decision") == "require_approval":
            request_summary = (
                f"{customer.name} requested refund help for failed transaction "
                f"{matched[0].get('reference', 'unknown')} (${first_amount:.2f})."
            )
            approval_id = policy_engine.create_approval_request(
                user_id=current_user.id,
                action="process_refund",
                system="support",
                request_data={
                    "ticket_id": ticket.id,
                    "customer_id": customer.id,
                    "request_summary": request_summary,
                    "transaction_reference": matched[0].get("reference"),
                    "amount": first_amount,
                    "customer_message": message_content,
                },
            )
            approval_payload = {
                "required": True,
                "approval_id": approval_id,
                "status": "pending",
                "request_summary": request_summary,
                "actions": ["approve", "reject"],
            }

        message = (
            "However, I found a matching failed transaction and can help with the refund process. "
            "To protect company privacy and security controls, I will only share customer-safe status updates here. "
        )
        if approval_payload:
            message += "An admin approval is required before the refund can be executed."
        else:
            message += "No additional approval is required at this stage."

        return {
            "message": _prepend_polite_response(message_content, message, escalation=True),
            "metadata": {
                "checked_transactions": True,
                "checked_transaction_count": len(transactions),
                "matched_failed_transactions": len(matched),
                "matched_transactions": matched[:3],
                "used_knowledge_base": False,
                "approval": approval_payload,
            },
        }

    if intent_is_breakdown:
        breakdown = _build_financial_breakdown_message(message_content, transactions)
        breakdown["message"] = _prepend_polite_response(message_content, breakdown["message"])
        return breakdown

    # Guardrail for generic support requests: do not expose internal policy text.
    base_message = (
        "I verified your account context. "
        "Please share a transaction reference, amount, or date range so I can provide a precise update "
        "without exposing internal company privacy details."
    )

    return {
        "message": _prepend_polite_response(message_content, base_message),
        "metadata": {
            "checked_transactions": True,
            "checked_transaction_count": len(transactions),
            "used_knowledge_base": False,
        },
    }


# ============================================================================
# TICKET ENDPOINTS
# ============================================================================

@router.post("/tickets", response_model=SupportTicketResponse)
async def create_support_ticket(
    request: SupportTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new support ticket."""
    # Verify customer exists
    customer = db.query(Customer).filter(Customer.id == request.customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    policy_engine = PolicyEngine(db)

    # Check policy
    decision = policy_engine.evaluate_action(
        user_id=current_user.id,
        action="create_ticket",
        system="support",
        context={"role": current_user.role}
    )

    if decision["decision"] == "deny":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision["reason"]
        )

    # Generate ticket number
    ticket_count = db.query(SupportTicket).count()
    ticket_number = f"TKT-{str(ticket_count + 1).zfill(6)}"

    ticket = SupportTicket(
        ticket_number=ticket_number,
        customer_id=request.customer_id,
        subject=request.subject,
        description=request.description,
        priority=request.priority,
        category=request.category,
        status=TicketStatusEnum.OPEN.value
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Log action
    policy_engine.log_action(
        user_id=current_user.id,
        action="create_ticket",
        system="support",
        resource=f"ticket:{ticket.id}",
        method="POST",
        status="success",
        result={"ticket_id": ticket.id, "ticket_number": ticket.ticket_number}
    )

    return ticket


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def get_support_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get support ticket details."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    return ticket


@router.get("/tickets", response_model=List[SupportTicketResponse])
async def list_support_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    customer_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List support tickets with optional filtering."""
    query = db.query(SupportTicket)

    if status_filter:
        query = query.filter(SupportTicket.status == status_filter)
    if customer_id:
        query = query.filter(SupportTicket.customer_id == customer_id)

    tickets = query.offset(skip).limit(limit).all()
    return tickets


@router.put("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def update_support_ticket(
    ticket_id: int,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update support ticket."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    policy_engine = PolicyEngine(db)

    # Check policy for status change
    if status:
        decision = policy_engine.evaluate_action(
            user_id=current_user.id,
            action="update_ticket_status",
            system="support",
            context={"role": current_user.role}
        )

        if decision["decision"] == "deny":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision["reason"]
            )

        ticket.status = status

        if status == TicketStatusEnum.RESOLVED.value:
            ticket.resolved_at = datetime.utcnow()

    if priority:
        ticket.priority = priority

    if assigned_to is not None:
        ticket.assigned_to = assigned_to

    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)

    # Log action
    policy_engine.log_action(
        user_id=current_user.id,
        action="update_ticket",
        system="support",
        resource=f"ticket:{ticket.id}",
        method="PUT",
        status="success"
    )

    return ticket


# ============================================================================
# MESSAGE ENDPOINTS
# ============================================================================

@router.post("/tickets/{ticket_id}/messages", response_model=MessageResponse)
async def add_ticket_message(
    ticket_id: int,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a message to a support ticket."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    if request.ticket_id != ticket_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket ID mismatch"
        )

    message = Message(
        ticket_id=ticket_id,
        sender_type=MessageSenderEnum.AGENT.value,
        sender_user_id=current_user.id,
        content=request.content,
        is_internal=request.is_internal
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    # Update ticket's last activity
    ticket.updated_at = datetime.utcnow()
    db.commit()

    return message


@router.get("/tickets/{ticket_id}/messages", response_model=List[MessageResponse])
async def get_ticket_messages(
    ticket_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get messages for a support ticket."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    _assert_ticket_access(ticket, current_user, db)

    query = db.query(Message).filter(Message.ticket_id == ticket_id)
    if not _is_admin(current_user):
        query = query.filter(Message.is_internal == False)

    messages = query.order_by(Message.created_at.desc()).offset(skip).limit(limit).all()
    if not _is_admin(current_user):
        messages = [
            message
            for message in messages
            if (message.custom_metadata or {}).get("event") != "chat_mode_change"
        ]

    return messages


@router.post("/tickets/{ticket_id}/customer-message", response_model=MessageResponse)
async def add_customer_message(
    ticket_id: int,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a customer message to a support ticket."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    message = Message(
        ticket_id=ticket_id,
        sender_type=MessageSenderEnum.CUSTOMER.value,
        sender_customer_id=ticket.customer_id,
        content=request.content,
        is_internal=False
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    # Update ticket status to waiting for response
    ticket.status = TicketStatusEnum.IN_PROGRESS.value
    ticket.updated_at = datetime.utcnow()
    db.commit()

    return message


def _generate_refund_suggestion(content: str, ticket: SupportTicket, customer: Customer) -> Dict[str, Any]:
    """Generate a suggested customer-facing reply when a refund/cancellation is detected.

    This is a deterministic template that asks for the required details and outlines
    backend verification steps for the support agent.
    """
    content_lower = (content or "").lower()
    keywords = ["refund", "cancelled", "cancel", "reimburse", "chargeback"]
    if not any(k in content_lower for k in keywords):
        return {"match": False}

    reply = (
        "Thank you for contacting support — I can help with that. "
        "To locate and process the refund for the cancelled 2025 transaction, please reply with the following: "
        "transaction ID (or order number), date of the transaction, billed amount, and the email or phone on the account."
    )

    requested_info = [
        "Transaction ID / Order number",
        "Transaction date",
        "Billed amount",
        "Account email or phone",
        "Any supporting docs (cancellation confirmation, receipts)"
    ]

    backend_steps = [
        "Search transactions table for the provided transaction ID + account.",
        "Confirm status == 'cancelled' and whether a refund was already issued.",
        "Check cancellation reason and refund eligibility window.",
        "If eligible, create refund request with payment provider and record refund_id in DB.",
        "Notify customer with refund confirmation and expected timeline (5–10 business days)."
    ]

    suggestion = {
        "match": True,
        "reply": reply,
        "requested_info": requested_info,
        "backend_steps": backend_steps,
    }

    # Store a short-lived session memory so subsequent requests in this session can reference it
    try:
        cache = get_cache()
        session_key = CacheKey.user_session(customer.id) + f":ticket:{ticket.id}"
        cache.set(session_key, {"last_refund_inquiry": {
            "ticket_id": ticket.id,
            "customer_id": customer.id,
            "snippet": content[:400],
            "timestamp": datetime.utcnow().isoformat()
        }}, ttl=3600)
    except Exception:
        # Non-fatal: caching failure should not block suggestion flow
        pass

    return suggestion


def _should_enrich_with_policy_rag(message_content: str) -> bool:
    """Use RAG only when users ask for policy/procedure documentation details."""
    lowered = (message_content or "").lower()
    policy_keywords = (
        "policy",
        "procedure",
        "guideline",
        "compliance",
        "terms",
        "documentation",
        "what is the rule",
        "show me the policy",
    )
    return any(keyword in lowered for keyword in policy_keywords)


@router.post("/tickets/{ticket_id}/suggested-reply")
async def suggested_reply(
    ticket_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a suggested customer-facing reply and backend steps for refund/cancellation requests.

    Payload expected: {"message": "..."}
    """
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    customer = db.query(Customer).filter(Customer.id == ticket.customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    message_content = payload.get("message", "")

    suggestion = _generate_refund_suggestion(message_content, ticket, customer)

    # If refund/cancellation detected, enrich with RAG only for explicit policy/procedure intent.
    try:
        if suggestion.get("match") and _should_enrich_with_policy_rag(message_content):
            # Query the corpus for relevant refund / failed transaction policy
            query_text = f"refund policy failed transaction {message_content[:400]}"

            # Run RAG query and attach the raw result
            try:
                rag_result = rag_query(query=query_text)
                suggestion["policy_search"] = rag_result
                logger.debug("suggested_reply rag_query result: %s", rag_result)
            except Exception as e:
                suggestion["policy_search"] = {"status": "error", "message": f"policy search failed: {str(e)}"}

            # Retrieve corpus info (file list) and attach for verification
            try:
                corpus_info = get_corpus_info()
                suggestion["corpus_info"] = corpus_info
                files = corpus_info.get("files", []) if isinstance(corpus_info, dict) else []
                file_names = [f.get("display_name") or f.get("source_uri") or f.get("file_id") for f in files]
                suggestion["corpus_files"] = file_names
                logger.debug("suggested_reply corpus files: %s", file_names)
                logger.debug("suggested_reply get_corpus_info result: %s", corpus_info)
            except Exception as e:
                suggestion["corpus_info"] = {"status": "error", "message": f"corpus info failed: {str(e)}"}
        elif suggestion.get("match"):
            suggestion["policy_search"] = {
                "status": "skipped",
                "message": "Policy enrichment skipped for cost optimization; no explicit policy/procedure intent detected.",
            }
    except Exception:
        # Non-fatal: don't block main flow on unexpected errors
        pass

    return {
        "ticket_id": ticket.id,
        "suggestion": suggestion,
    }


@router.get("/chat/bootstrap")
async def chat_bootstrap(
    ticket_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bootstrap support chat for customer or admin users."""
    if _is_admin(current_user):
        conversations = _build_conversation_summary_list(db)
        selected_ticket = None

        if ticket_id is not None:
            selected_ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        elif conversations:
            selected_ticket = db.query(SupportTicket).filter(SupportTicket.id == conversations[0]["ticket_id"]).first()

        if not selected_ticket:
            return {
                "viewer": {
                    "id": current_user.id,
                    "role": current_user.role,
                    "name": current_user.name,
                },
                "ticket": None,
                "messages": [],
                "conversations": conversations,
            }

        customer = _get_customer_for_ticket(selected_ticket, db)
        messages = db.query(Message).filter(
            Message.ticket_id == selected_ticket.id
        ).order_by(Message.created_at.asc()).all()
        approval_lookup = _build_approval_lookup(messages, db)

        return {
            "viewer": {
                "id": current_user.id,
                "role": current_user.role,
                "name": current_user.name,
            },
            "ticket": _build_ticket_payload(selected_ticket, customer),
            "messages": [_serialize_message(m, approval_lookup) for m in messages],
            "conversations": conversations,
        }

    customer = _ensure_customer_for_user(current_user, db)
    ticket = _ensure_active_chat_ticket(customer, db)
    messages = db.query(Message).filter(
        Message.ticket_id == ticket.id,
        Message.is_internal == False,
    ).order_by(Message.created_at.asc()).all()
    messages = [
        message
        for message in messages
        if (message.custom_metadata or {}).get("event") != "chat_mode_change"
    ]
    approval_lookup = _build_approval_lookup(messages, db)

    return {
        "viewer": {
            "id": current_user.id,
            "role": current_user.role,
            "name": current_user.name,
        },
        "ticket": _build_ticket_payload(ticket, customer),
        "messages": [_serialize_message(m, approval_lookup) for m in messages],
        "conversations": [],
    }


@router.get("/chat/admin/conversations")
async def list_admin_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all user conversations for support admins."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    return {
        "conversations": _build_conversation_summary_list(db),
    }


@router.post("/chat/tickets/{ticket_id}/message")
async def send_chat_message(
    ticket_id: int,
    request: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a chat message and optionally produce an agent response."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    _assert_ticket_access(ticket, current_user, db)
    ticket_metadata = ticket.custom_metadata or {}
    chat_mode = ticket_metadata.get("chat_mode", "agent")
    customer = _get_customer_for_ticket(ticket, db)

    if _is_admin(current_user):
        admin_message = Message(
            ticket_id=ticket.id,
            sender_type=MessageSenderEnum.AGENT.value,
            sender_user_id=current_user.id,
            content=request.content,
            is_internal=request.is_internal,
            custom_metadata={"source": "human_support"},
        )
        db.add(admin_message)
        ticket.updated_at = datetime.utcnow()
        ticket.status = TicketStatusEnum.IN_PROGRESS.value
        db.commit()
        db.refresh(admin_message)
        db.refresh(ticket)

        return {
            "ticket": _build_ticket_payload(ticket, customer),
            "message": _serialize_message(admin_message),
            "agent_message": None,
        }

    customer_message = Message(
        ticket_id=ticket.id,
        sender_type=MessageSenderEnum.CUSTOMER.value,
        sender_customer_id=ticket.customer_id,
        content=request.content,
        is_internal=False,
    )
    db.add(customer_message)
    db.flush()

    agent_message: Optional[Message] = None
    if chat_mode == "human":
        ticket.status = TicketStatusEnum.WAITING_CUSTOMER.value
    else:
        agent_reply = _generate_support_agent_reply(
            ticket=ticket,
            customer=customer,
            current_user=current_user,
            message_content=request.content,
            db=db,
        )
        agent_message = Message(
            ticket_id=ticket.id,
            sender_type=MessageSenderEnum.AGENT.value,
            sender_user_id=None,
            content=agent_reply["message"],
            is_internal=False,
            custom_metadata=agent_reply.get("metadata") or {},
        )
        db.add(agent_message)

        _compact_ticket_context(ticket, request.content, agent_reply["message"])
        _write_support_cache_memory(customer.id, ticket.id, request.content, agent_reply["message"])
        ticket.status = TicketStatusEnum.IN_PROGRESS.value

    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(customer_message)
    db.refresh(ticket)
    if agent_message is not None:
        db.refresh(agent_message)

    return {
        "ticket": _build_ticket_payload(ticket, customer),
        "message": _serialize_message(customer_message),
        "agent_message": _serialize_message(agent_message) if agent_message else None,
    }


@router.post("/chat/tickets/{ticket_id}/takeover")
async def update_chat_mode(
    ticket_id: int,
    request: ChatModeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable or disable human-in-the-loop takeover for a support ticket."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    if request.mode not in {"agent", "human"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be 'agent' or 'human'")

    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    metadata = ticket.custom_metadata or {}
    metadata["chat_mode"] = request.mode
    metadata["last_mode_change"] = {
        "mode": request.mode,
        "changed_by": current_user.email,
        "changed_at": datetime.utcnow().isoformat(),
        "note": request.note,
    }
    ticket.custom_metadata = metadata
    ticket.updated_at = datetime.utcnow()

    mode_message = Message(
        ticket_id=ticket.id,
        sender_type=MessageSenderEnum.SYSTEM.value,
        content=(
            f"Support mode switched to {request.mode.upper()} by {current_user.name or current_user.email}."
            + (f" Note: {request.note}" if request.note else "")
        ),
        is_internal=True,
        custom_metadata={"event": "chat_mode_change", "mode": request.mode, "visibility": "admin_only"},
    )
    db.add(mode_message)
    db.commit()
    db.refresh(mode_message)

    customer = _get_customer_for_ticket(ticket, db)
    return {
        "ticket": _build_ticket_payload(ticket, customer),
        "message": _serialize_message(mode_message),
    }


@router.post("/chat/tickets/{ticket_id}/approvals/{approval_id}")
async def handle_chat_approval(
    ticket_id: int,
    approval_id: int,
    request: ChatApprovalDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve/reject a pending support approval directly from chat."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    if request.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="decision must be 'approve' or 'reject'")

    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    if approval.status != ApprovalStatusEnum.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval already resolved with status: {approval.status}",
        )

    approval.status = ApprovalStatusEnum.APPROVED.value if request.decision == "approve" else ApprovalStatusEnum.DENIED.value
    approval.approved_by = current_user.email
    approval.reason = request.reason or ("Approved from support chat" if request.decision == "approve" else "Rejected from support chat")
    approval.resolved_at = datetime.utcnow()

    if request.decision == "approve" and approval.action == "process_refund" and approval.system in {"financial", "support"}:
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to finalize refund approval: {str(exc)}"
            ) from exc

    event_message = Message(
        ticket_id=ticket.id,
        sender_type=MessageSenderEnum.SYSTEM.value,
        content=(
            f"Admin {current_user.name or current_user.email} {request.decision}d approval #{approval.id}."
            f" Reason: {approval.reason}"
        ),
        is_internal=False,
        custom_metadata={
            "event": "approval_decision",
            "approval_id": approval.id,
            "decision": request.decision,
            "reason": approval.reason,
        },
    )
    db.add(event_message)
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event_message)

    customer = _get_customer_for_ticket(ticket, db)
    return {
        "approval_id": approval.id,
        "status": approval.status,
        "ticket": _build_ticket_payload(ticket, customer),
        "message": _serialize_message(event_message),
    }
