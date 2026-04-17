"""Support domain agent tools."""
from typing import Optional, Dict, Any, List
from agent_utils import AgentContext, BackendAPIClient, format_date


async def handle_ticket_creation(
    ctx: AgentContext,
    customer_id: int,
    subject: str,
    description: str,
    priority: str = "medium",
    category: Optional[str] = None,
) -> str:
    """
    Create a new support ticket.
    
    RULE: Calls BACKEND /api/support/tickets
    """
    ctx.log_step({
        "action": "ticket_creation",
        "customer_id": customer_id,
        "subject": subject,
        "priority": priority,
    })

    result = await ctx.client.post(
        "/api/support/tickets",
        {
            "customer_id": customer_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "category": category,
        }
    )

    if result.get("error"):
        ctx.log_step({
            "action": "ticket_creation",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to create ticket: {result.get('detail')}"

    ticket = result
    ctx.log_step({
        "action": "ticket_creation",
        "status": "success",
        "ticket_id": ticket.get("id"),
        "ticket_number": ticket.get("ticket_number"),
    })

    return f"""
✅ **Support Ticket Created**

- **Ticket Number:** {ticket.get('ticket_number')}
- **Subject:** {ticket.get('subject')}
- **Priority:** {ticket.get('priority')}
- **Status:** {ticket.get('status')}
- **Created:** {format_date(ticket.get('created_at'))}

Your ticket has been created and assigned to our support team. You'll receive updates as we work on your issue.
"""


async def handle_ticket_update(
    ctx: AgentContext,
    ticket_id: int,
    status: Optional[str] = None,
    priority: Optional[str] = None,
) -> str:
    """
    Update a support ticket's status or priority.
    
    RULE: Calls BACKEND /api/support/tickets/{ticket_id}
    """
    ctx.log_step({
        "action": "ticket_update",
        "ticket_id": ticket_id,
        "status": status,
        "priority": priority,
    })

    update_data = {}
    if status:
        update_data["status"] = status
    if priority:
        update_data["priority"] = priority

    result = await ctx.client.put(
        f"/api/support/tickets/{ticket_id}",
        update_data
    )

    if result.get("error"):
        ctx.log_step({
            "action": "ticket_update",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to update ticket: {result.get('detail')}"

    ticket = result
    ctx.log_step({
        "action": "ticket_update",
        "status": "success",
    })

    return f"""
✅ **Ticket Updated**

- **Ticket:** {ticket.get('ticket_number')}
- **New Status:** {ticket.get('status')}
- **Last Updated:** {format_date(ticket.get('updated_at'))}
"""


async def handle_ticket_query(
    ctx: AgentContext,
    customer_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Query support tickets for a customer.
    
    RULE: Calls BACKEND /api/support/tickets
    """
    ctx.log_step({
        "action": "ticket_query",
        "customer_id": customer_id,
        "status": status_filter,
    })

    params = {"limit": limit}
    if customer_id:
        params["customer_id"] = customer_id
    if status_filter:
        params["status"] = status_filter

    result = await ctx.client.get("/api/support/tickets", params=params)

    if result.get("error"):
        ctx.log_step({
            "action": "ticket_query",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to query tickets: {result.get('detail')}"

    tickets = result if isinstance(result, list) else result.get("tickets", [])

    if not tickets:
        return "📭 No support tickets found"

    response = "📋 **Support Tickets**\n\n"

    for ticket in tickets:
        response += f"""- **{ticket['ticket_number']}**: {ticket['subject']}
  - Status: {ticket['status']} | Priority: {ticket['priority']}
  - Created: {format_date(ticket['created_at'])}
  
"""

    ctx.log_step({
        "action": "ticket_query",
        "status": "success",
        "ticket_count": len(tickets),
    })

    return response


async def handle_message_addition(
    ctx: AgentContext,
    ticket_id: int,
    content: str,
    is_internal: bool = False,
) -> str:
    """
    Add a message to a support ticket.
    
    RULE: Calls BACKEND /api/support/tickets/{ticket_id}/messages
    """
    ctx.log_step({
        "action": "message_addition",
        "ticket_id": ticket_id,
        "is_internal": is_internal,
    })

    result = await ctx.client.post(
        f"/api/support/tickets/{ticket_id}/messages",
        {
            "ticket_id": ticket_id,
            "content": content,
            "is_internal": is_internal,
        }
    )

    if result.get("error"):
        ctx.log_step({
            "action": "message_addition",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to add message: {result.get('detail')}"

    message = result
    ctx.log_step({
        "action": "message_addition",
        "status": "success",
    })

    return f"""
✅ **Message Added to Ticket {ticket_id}**

- **Sender Type:** {message.get('sender_type')}
- **Internal:** {'Yes' if message.get('is_internal') else 'No'}
- **Added:** {format_date(message.get('created_at'))}
"""


async def execute_support_tool(
    ctx: AgentContext,
    tool_name: str,
    **kwargs
) -> str:
    """
    Execute support domain tools through backend APIs.
    
    This is the main router for support operations.
    All operations MUST go through the backend.
    """
    
    if tool_name == "create_ticket":
        return await handle_ticket_creation(ctx, **kwargs)
    
    elif tool_name == "query_tickets":
        return await handle_ticket_query(ctx, **kwargs)
    
    elif tool_name == "update_ticket":
        return await handle_ticket_update(ctx, **kwargs)
    
    elif tool_name == "add_message":
        return await handle_message_addition(ctx, **kwargs)
    
    else:
        return f"❌ Unknown support tool: {tool_name}"
