# ARCHITECTURE & IMPLEMENTATION DETAILS

## System Design

### High-Level Data Flow

```
┌─────────────┐
│   User      │
│ Interface   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  Agent Command (Query)          │
│  "Process $500 refund"          │
└──────┬──────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│ POLICY ENGINE                                │
│ - Parse request (action, system, amount)     │
│ - Load policy from database                  │
│ - Evaluate conditions                        │
│ Decision Point:                              │
│ ├─ ALLOW ────────────────────┐               │
│ ├─ REQUIRE_APPROVAL ──────┐   │               │
│ └─ DENY ──────────────────┤───┼────┐         │
└──────────────────────────┼───┼────┼─────────┘
                           │   │    │
         ┌─────────────────┘   │    │
         │                     │    │
         ▼                     ▼    ▼
    ┌────────────┐      ┌──────────────────┐
    │ TOKEN VAULT│      │ APPROVAL REQUEST │
    │            │      │ (Workflow)       │
    │ Issue      │      │ Created          │
    │ Scoped     │      │ Waiting for      │
    │ Token      │      │ Human Decision   │
    └─────┬──────┘      └──────┬───────────┘
          │                    │
          ▼                    ▼
    ┌────────────┐      ┌──────────────────┐
    │ MCP Tool   │      │ Approval Modal   │
    │ Execution  │      │ (UI)             │
    │ (with      │      │ ┌──────────────┐ │
    │  token)    │      │ │ Approve      │ │
    │            │      │ │ Button       │ │
    └─────┬──────┘      │ │              │ │
          │             │ │ Deny Button  │ │
          ▼             │ └──────────────┘ │
    ┌────────────┐      └──────┬───────────┘
    │ Data/      │             │
    │ Result     │             ▼
    └─────┬──────┘      ┌──────────────────┐
          │             │ Re-execute with  │
          │             │ granted token    │
          │             └──────┬───────────┘
          │                    │
          └──────────┬─────────┘
                     ▼
          ┌──────────────────────┐
          │ AUDIT LOG            │
          │ - User               │
          │ - Action             │
          │ - Status (success/   │
          │   blocked/failure)   │
          │ - Timestamp          │
          │ - Result data        │
          └──────────────────────┘
                     ▼
          ┌──────────────────────┐
          │ Display Result       │
          │ in UI                │
          └──────────────────────┘
```

## Component Interactions

### 1. Authentication Flow
```
User Login
    ↓
FastAPI /api/auth/login
    ↓
Mock Auth0 verification
    ↓
Create JWT token
    ↓
Store in frontend localStorage
    ↓
Auto-include in all subsequent requests
    ↓
Verified by get_current_user dependency
```

### 2. Agent Execution Flow
```
AgentPanel Input (frontend)
    ↓
POST /api/agent/execute
    ↓
PolicyEngine.evaluate_action()
    ↓
    ├─→ ALLOW
    │   ├─→ TokenVault.create_token()
    │   ├─→ tool_registry.execute_tool_method()
    │   ├─→ policy_engine.log_action(status=success)
    │   └─→ Return result with token
    │
    ├─→ REQUIRE_APPROVAL
    │   ├─→ policy_engine.create_approval_request()
    │   ├─→ policy_engine.log_action(status=pending_approval)
    │   └─→ Return approval_id, waiting for human
    │
    └─→ DENY
        ├─→ policy_engine.log_action(status=blocked)
        └─→ Return error message
```

### 3. Approval Resolution Flow
```
Admin reviews pending approval in UI
    ↓
ApprovalModal shows request details
    ↓
Admin clicks "Approve" or "Deny"
    ↓
POST /api/approval/{id}/resolve
    ↓
policy_engine.resolve_approval()
    ↓
Update approval.status in database
    ↓
Optional: Agent re-executes with granted token
    ↓
Audit logged with approval chain
```

## Database Schema Relationships

```
┌─────────────┐
│   Users     │
│ ┌─────────┐ │
│ │ id (PK) │ │
│ │ email   │ │────────┐
│ │ auth0_id│ │        │
│ └─────────┘ │        │ 1:N
└─────────────┘        │
                       ↓
              ┌─────────────────┐
              │     Tokens      │
              │ ┌─────────────┐ │
              │ │ id (PK)     │ │
              │ │ user_id (FK)│ │
              │ │ token_id    │ │
              │ │ scope       │ │
              │ │ expires_at  │ │
              │ └─────────────┘ │
              └─────────────────┘

┌──────────────┐
│   Policies   │
│ ┌──────────┐ │
│ │ id (PK)  │ │
│ │ name     │ │
│ │ action   │ │
│ │ rule     │ │ ◄──Queried by Policy Engine
│ │ condition│ │
│ └──────────┘ │
└──────────────┘

┌──────────────┐
│ Approvals    │
│ ┌──────────┐ │    ┌──────────┐
│ │ id (PK)  │ │───→│  Users   │
│ │user_id(FK)│    │ (approver)
│ │ action   │ │
│ │ status   │ │
│ │ expires  │ │
│ └──────────┘ │
└──────────────┘

┌──────────────┐
│ AuditLogs    │
│ ┌──────────┐ │
│ │ id (PK)  │ │
│ │user_id(FK)│───→┌──────────┐
│ │ action   │ │   │   Users  │
│ │ status   │ │   └──────────┘
│ │ created  │ │
│ │ result   │ │
│ └──────────┘ │
└──────────────┘
```

## API Endpoint Hierarchy

```
/api/
├─ /auth
│  ├─ POST   /login           (user credentials)
│  ├─ POST   /register        (new user)
│  └─ GET    /me              (current user)
│
├─ /agent
│  ├─ POST   /execute         (main action)
│  ├─ GET    /tools           (list MCP tools)
│  ├─ GET    /tokens          (user's tokens)
│  └─ POST   /token-request   (request token)
│
├─ /policy
│  ├─ GET    /list            (all policies)
│  ├─ GET    /check           (check action)
│  ├─ GET    /dashboard       (policy stats)
│  └─ GET    /demo            (example policies)
│
├─ /approval
│  ├─ GET    /pending         (user's pending)
│  ├─ GET    /{id}            (specific approval)
│  ├─ POST   /{id}/resolve    (approve/deny)
│  └─ GET    /                (all approvals)
│
└─ /audit
   ├─ GET    /logs            (all logs)
   ├─ GET    /logs/summary    (statistics)
   └─ GET    /logs/by-system  (grouped)
```

## Frontend Component Tree

```
RootLayout
├─ Navbar
├─ Sidebar
└─ Main Content

  DashboardLayout (auth protected)
  ├─ Dashboard
  │  ├─ AgentPanel
  │  ├─ TokenDisplay
  │  ├─ ApprovalModal
  │  └─ Metrics Cards
  │
  ├─ /financial
  │  ├─ AgentPanel
  │  ├─ Quick Stats
  │  └─ Transactions List
  │
  ├─ /support
  │  ├─ AgentPanel
  │  └─ Support Features
  │
  ├─ /erp
  │  ├─ AgentPanel
  │  └─ ERP Features
  │
  ├─ /policy
  │  ├─ Policy Cards
  │  ├─ System Filters
  │  └─ Policy Flow Diagram
  │
  ├─ /approvals
  │  ├─ Status Filters
  │  ├─ Approval List
  │  └─ ApprovalModal
  │
  └─ /audit
     ├─ Log Table
     ├─ Filters
     └─ Statistics
```

## Security Layers

### Layer 1: Authentication
```
┌────────────────────────────────┐
│ JWT Token                      │
│ - Issued by /api/auth/login   │
│ - Stored in localStorage      │
│ - Auto-included in requests   │
│ - Verified by endpoint        │
└────────────────────────────────┘
```

### Layer 2: Authorization
```
┌────────────────────────────────┐
│ Policy Engine                  │
│ - Evaluates every action      │
│ - Checks conditions            │
│ - Creates approval requests   │
└────────────────────────────────┘
```

### Layer 3: Delegation
```
┌────────────────────────────────┐
│ Token Vault                    │
│ - Creates scoped tokens       │
│ - Time-limited (1 hour)       │
│ - Verified for scope          │
│ - Never exposes raw creds     │
└────────────────────────────────┘
```

### Layer 4: Audit
```
┌────────────────────────────────┐
│ Audit Log                      │
│ - Every action recorded       │
│ - Success/failure/blocked     │
│ - User identity               │
│ - Timestamp and details       │
└────────────────────────────────┘
```

## Policy Decision Tree

```
Request Arrives: { action, system, context }
        ↓
Find matching policy
        ├─→ Not found
        │   └─→ DENY (fail safe)
        │
        └─→ Found
            ├─→ Rule: "allow"
            │   ├─→ Issue token
            │   ├─→ Execute immediately
            │   └─→ Log: "success"
            │
            ├─→ Rule: "deny"
            │   ├─→ Block action
            │   └─→ Log: "blocked" + reason
            │
            └─→ Rule: "require_approval"
                ├─→ Evaluate conditions
                │   ├─→ Conditions met
                │   │   ├─→ Issue token
                │   │   ├─→ Execute immediately
                │   │   └─→ Log: "success"
                │   │
                │   └─→ Conditions not met
                │       ├─→ Create approval request
                │       └─→ Log: "pending_approval"
```

## Token Lifecycle

```
1. Request
   POST /api/agent/execute
   { action: "process_refund", amount: 150 }
        ↓
2. Policy Check
   Policy engine evaluates → ALLOW
        ↓
3. Token Creation
   POST /api/agent/token-request
   Vault generates: vault_xyz123abc...
   Stored in DB:
   - token_id: xyz123abc
   - scope: write:support
   - system: support
   - expires_at: +1 hour from now
        ↓
4. Tool Execution
   Send token with MCP call:
   process_refund(token="vault_xyz123abc...", ...)
        ↓
5. Token Verification
   Token Vault checks:
   - Is it in vault storage?
   - Is it expired?
   - Does scope match required scope?
        ↓
6. Tool Execution
   Token verified → Execute action
        ↓
7. Token Revocation (optional)
   After action completes, token can be revoked
   or left to expire naturally (1 hour)
```

## Approval Lifecycle

```
1. Action Requires Approval
   Policy decision: REQUIRE_APPROVAL
        ↓
2. Create Approval Request
   Insert into Approvals table:
   - id: 42
   - user_id: 3
   - action: process_refund
   - request_data: { ticket_id: 1, amount: 250 }
   - status: pending
   - expires_at: now + 30 minutes
        ↓
3. User Notified
   Frontend shows: "Approval #42 - process_refund"
   Approval modal displays request details
        ↓
4. Human Review
   Admin clicks: Approve or Deny
        ↓
5. Resolve Approval
   Update Approvals table:
   - status: approved
   - approved_by: admin@example.com
   - resolved_at: now
        ↓
6. Execute Action
   If approved:
   - Issue token from vault
   - Execute MCP tool
   - Log success
   
   If denied:
   - Log denial
   - No execution
        ↓
7. Cleanup
   Approval expires after TTL
   or resolved status persists for audit
```

---

This document provides the technical blueprint for understanding how every component works together to create a secure, auditable AI agent platform.
