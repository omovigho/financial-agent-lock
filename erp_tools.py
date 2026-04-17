"""ERP domain agent tools."""
from typing import Optional, Dict, Any
from agent_utils import AgentContext, BackendAPIClient, format_currency, format_date


async def handle_purchase_order_creation(
    ctx: AgentContext,
    vendor: str,
    amount: int,
    currency: str = "USD",
    description: Optional[str] = None,
    category: Optional[str] = None,
) -> str:
    """
    Create a purchase order.
    
    RULE: Calls BACKEND /api/erp/purchase-orders
    RULE: Backend will handle policy evaluation and approval if needed
    """
    ctx.log_step({
        "action": "po_creation",
        "vendor": vendor,
        "amount": amount,
        "category": category,
    })

    result = await ctx.client.post(
        "/api/erp/purchase-orders",
        {
            "vendor": vendor,
            "amount": amount,
            "currency": currency,
            "description": description,
            "category": category,
        }
    )

    if result.get("error"):
        status_code = result.get("status_code")
        
        if status_code == 202:
            # Approval required
            approval_id = result.get("approval_id")
            ctx.log_step({
                "action": "po_creation",
                "status": "approval_pending",
                "approval_id": approval_id,
            })
            return f"""
⏳ **Purchase Order Approval Required**

Your purchase order has been created but requires approval.

- **Vendor:** {vendor}
- **Amount:** {format_currency(amount)}
- **Approval ID:** {approval_id}
- **Category:** {category or 'General'}

An administrator will review and approve this order. Processing will continue once approved.
"""
        else:
            ctx.log_step({
                "action": "po_creation",
                "status": "failed",
                "reason": result.get("detail"),
            })
            return f"❌ PO creation failed: {result.get('detail')}"

    # PO created successfully
    po = result
    ctx.log_step({
        "action": "po_creation",
        "status": "success",
        "po_id": po.get("id"),
        "po_number": po.get("po_number"),
    })

    return f"""
✅ **Purchase Order Created**

- **PO Number:** {po.get('po_number')}
- **Vendor:** {po.get('vendor')}
- **Amount:** {format_currency(po.get('amount'))}
- **Status:** {po.get('status')}
- **Date:** {format_date(po.get('created_at'))}

The purchase order has been created and is ready for processing.
"""


async def handle_purchase_order_query(
    ctx: AgentContext,
    status_filter: Optional[str] = None,
    vendor: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Query purchase orders.
    
    RULE: Calls BACKEND /api/erp/purchase-orders
    """
    ctx.log_step({
        "action": "po_query",
        "status": status_filter,
        "vendor": vendor,
    })

    params = {"limit": limit}
    if status_filter:
        params["status"] = status_filter
    if vendor:
        params["vendor"] = vendor

    result = await ctx.client.get("/api/erp/purchase-orders", params=params)

    if result.get("error"):
        ctx.log_step({
            "action": "po_query",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to query purchase orders: {result.get('detail')}"

    pos = result if isinstance(result, list) else result.get("purchase_orders", [])

    if not pos:
        return "📭 No purchase orders found"

    response = "📋 **Purchase Orders**\n\n"

    for po in pos:
        response += f"""- **{po['po_number']}**: {po['vendor']}
  - Amount: {format_currency(po['amount'])}
  - Status: {po['status']}
  - Created: {format_date(po['created_at'])}
  
"""

    ctx.log_step({
        "action": "po_query",
        "status": "success",
        "po_count": len(pos),
    })

    return response


async def handle_purchase_order_status(
    ctx: AgentContext,
    po_id: int,
) -> str:
    """
    Get the status of a purchase order.
    
    RULE: Calls BACKEND /api/erp/purchase-orders/{po_id}/status
    """
    ctx.log_step({
        "action": "po_status",
        "po_id": po_id,
    })

    result = await ctx.client.get(f"/api/erp/purchase-orders/{po_id}/status")

    if result.get("error"):
        ctx.log_step({
            "action": "po_status",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to get PO status: {result.get('detail')}"

    po = result
    ctx.log_step({
        "action": "po_status",
        "status": "success",
    })

    return f"""
📊 **Purchase Order Status**

- **PO Number:** {po.get('po_number')}
- **Current Status:** {po.get('status')}
- **Created:** {format_date(po.get('created_at'))}
- **Approved By:** {po.get('approved_by') or 'Pending'}
- **Resolved:** {format_date(po.get('resolved_at')) if po.get('resolved_at') else 'Pending'}
"""


async def handle_purchase_order_update(
    ctx: AgentContext,
    po_id: int,
    status: str,
) -> str:
    """
    Update a purchase order's status.
    
    RULE: Calls BACKEND /api/erp/purchase-orders/{po_id}
    """
    ctx.log_step({
        "action": "po_update",
        "po_id": po_id,
        "new_status": status,
    })

    result = await ctx.client.put(
        f"/api/erp/purchase-orders/{po_id}",
        {"status": status}
    )

    if result.get("error"):
        ctx.log_step({
            "action": "po_update",
            "status": "failed",
            "reason": result.get("detail"),
        })
        return f"❌ Failed to update PO: {result.get('detail')}"

    po = result
    ctx.log_step({
        "action": "po_update",
        "status": "success",
    })

    return f"""
✅ **Purchase Order Updated**

- **PO:** {po.get('po_number')}
- **New Status:** {po.get('status')}
- **Updated:** {format_date(po.get('created_at'))}
"""


async def execute_erp_tool(
    ctx: AgentContext,
    tool_name: str,
    **kwargs
) -> str:
    """
    Execute ERP domain tools through backend APIs.
    
    This is the main router for ERP operations.
    All operations MUST go through the backend.
    """
    
    if tool_name == "create_purchase_order":
        return await handle_purchase_order_creation(ctx, **kwargs)
    
    elif tool_name == "query_purchase_orders":
        return await handle_purchase_order_query(ctx, **kwargs)
    
    elif tool_name == "get_po_status":
        return await handle_purchase_order_status(ctx, **kwargs)
    
    elif tool_name == "update_purchase_order":
        return await handle_purchase_order_update(ctx, **kwargs)
    
    else:
        return f"❌ Unknown ERP tool: {tool_name}"
