"""Financial domain agent tools."""
from typing import Optional, Dict, Any
from google.adk.agents import agent as adk_agent
from agent_utils import AgentContext, BackendAPIClient, format_currency, format_date


async def handle_financial_analysis(
    ctx: AgentContext,
    customer_id: Optional[int] = None,
    account_id: Optional[int] = None,
) -> str:
    """
    Analyze financial data for a customer or account.
    
    RULE: Calls BACKEND /api/financial/accounts/{account_id}/analysis
    RULE: Never calls external financial APIs directly
    """
    ctx.log_step({
        "action": "financial_analysis_start",
        "customer_id": customer_id,
        "account_id": account_id,
    })

    if not account_id:
        return "❌ Error: account_id is required for financial analysis"

    # Call backend analysis endpoint
    result = await ctx.client.get(f"/api/financial/accounts/{account_id}/analysis")

    if result.get("error"):
        ctx.log_step({
            "action": "financial_analysis",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to analyze account: {result.get('detail')}"

    # Format response
    analysis = result
    response = f"""
📊 **Financial Analysis for Account {account_id}**

**Summary:**
- Total Credits: {format_currency(analysis['total_credit'])}
- Total Debits: {format_currency(analysis['total_debit'])}
- Net Balance: {format_currency(analysis['net_balance'])}
- Transaction Count: {analysis['transaction_count']}
- Currency: {analysis['currency']}

**Breakdown by Type:**
"""

    for trans_type, count in analysis["by_type"].items():
        response += f"- {trans_type}: {count} transactions\n"

    if analysis.get("date_range", {}).get("start"):
        response += f"\n**Date Range:** {format_date(analysis['date_range']['start'])} to {format_date(analysis['date_range']['end'])}"

    ctx.log_step({
        "action": "financial_analysis",
        "status": "success",
        "result": analysis,
    })

    return response


async def handle_refund_request(
    ctx: AgentContext,
    customer_id: int,
    transaction_id: int,
    amount: int,
    reason: str,
) -> str:
    """
    Process a refund request.
    
    RULE: Calls BACKEND /api/financial/refunds
    RULE: Backend will handle policy evaluation and approval if needed
    RULE: Never bypasses policy engine
    """
    ctx.log_step({
        "action": "refund_request_start",
        "customer_id": customer_id,
        "transaction_id": transaction_id,
        "amount": amount,
        "reason": reason,
    })

    # Call backend refund endpoint
    result = await ctx.client.post(
        "/api/financial/refunds",
        {
            "transaction_id": transaction_id,
            "customer_id": customer_id,
            "amount": amount,
            "reason": reason,
            "description": f"Agent-initiated refund for {reason}",
        }
    )

    if result.get("error"):
        status_code = result.get("status_code")
        
        if status_code == 202:
            # Approval required
            approval_id = result.get("approval_id")
            ctx.log_step({
                "action": "refund_request",
                "status": "approval_pending",
                "approval_id": approval_id,
            })
            return f"""
⏳ **Refund Approval Required**

Your refund request for {format_currency(amount)} has been created but requires approval.

- **Approval ID:** {approval_id}
- **Customer:** {customer_id}
- **Reason:** {reason}
- **Amount:** {format_currency(amount)}

An administrator will review and approve this request. You'll be notified once it's processed.
"""
        else:
            ctx.log_step({
                "action": "refund_request",
                "status": "failed",
                "reason": result.get("detail"),
            })
            return f"❌ Refund failed: {result.get('detail')}"

    # Refund processed successfully
    refund = result
    ctx.log_step({
        "action": "refund_request",
        "status": "success",
        "refund_id": refund.get("id"),
    })

    return f"""
✅ **Refund Processed**

- **Refund ID:** {refund.get('id')}
- **Amount:** {format_currency(refund.get('amount'))}
- **Status:** {refund.get('status')}
- **Date:** {format_date(refund.get('created_at'))}

The refund has been approved and is being processed.
"""


async def handle_transaction_query(
    ctx: AgentContext,
    account_id: int,
    limit: int = 10,
) -> str:
    """
    Query recent transactions for an account.
    
    RULE: Calls BACKEND /api/financial/accounts/{account_id}/transactions
    """
    ctx.log_step({
        "action": "transaction_query",
        "account_id": account_id,
        "limit": limit,
    })

    result = await ctx.client.get(
        f"/api/financial/accounts/{account_id}/transactions",
        params={"limit": limit}
    )

    if result.get("error"):
        ctx.log_step({
            "action": "transaction_query",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to query transactions: {result.get('detail')}"

    transactions = result if isinstance(result, list) else result.get("transactions", [])

    if not transactions:
        return f"📭 No transactions found for account {account_id}"

    response = f"📋 **Recent Transactions for Account {account_id}**\n\n"

    for trans in transactions:
        response += f"""- **{trans['transaction_type'].upper()}** ${trans['amount']/100:.2f}
  - Reference: {trans['reference']}
  - Status: {trans['status']}
  - Date: {format_date(trans['created_at'])}
  
"""

    ctx.log_step({
        "action": "transaction_query",
        "status": "success",
        "transaction_count": len(transactions),
    })

    return response


async def execute_financial_tool(
    ctx: AgentContext,
    tool_name: str,
    **kwargs
) -> str:
    """
    Execute financial domain tools through backend APIs.
    
    This is the main router for financial operations.
    All operations MUST go through the backend.
    """
    
    if tool_name == "analyze_transactions":
        return await handle_financial_analysis(ctx, **kwargs)
    
    elif tool_name == "request_refund":
        return await handle_refund_request(ctx, **kwargs)
    
    elif tool_name == "query_transactions":
        return await handle_transaction_query(ctx, **kwargs)
    
    else:
        return f"❌ Unknown financial tool: {tool_name}"
