# Agent-Lock

Secure AI operations platform for financial, support, and ERP workflows with policy enforcement, approval gates, scoped token delegation, and full auditability.

This project demonstrates how an AI-powered assistant can execute sensitive business actions safely by putting a policy engine and token vault between agent decisions and system execution.

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Architecture at a Glance](#architecture-at-a-glance)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Run with Docker](#run-with-docker)
- [Authentication and Access Model](#authentication-and-access-model)
- [Policy and Approval Model](#policy-and-approval-model)
- [API Overview](#api-overview)
- [Data Model Overview](#data-model-overview)
- [Operational Flows](#operational-flows)
- [Troubleshooting](#troubleshooting)
- [Known Repository Caveats](#known-repository-caveats)
- [Additional Documentation](#additional-documentation)
- [License](#license)

## What This Project Does

Agent-Lock is a full-stack reference implementation for secure AI orchestration.

Core capabilities:

- Policy-first execution for all agent actions.
- Human-in-the-loop approvals for risky operations.
- Scoped, time-limited token delegation through a token vault.
- End-to-end audit trail for actions, decisions, and outcomes.
- Domain support for:
  - Financial operations (transactions, refunds, account insights)
  - Support workflows (tickets, messaging, escalation handling)
  - ERP operations (purchase orders and status tracking)
- Optional Auth0 Token Vault exchange for provider tokens.
- Optional RAG-backed policy/context enrichment.

## Architecture at a Glance

### High-level request flow

1. User submits a request from the frontend.
2. Backend endpoint receives the action request.
3. Policy engine evaluates the action against active policies.
4. Decision branch:
   - `allow`: execute immediately.
   - `require_approval`: create approval request and wait for human decision.
   - `deny`: block action.
5. If executable, backend issues scoped token from token vault.
6. MCP tool executes operation with delegated token.
7. Result and decision are written to audit logs.
8. Frontend renders the outcome and approval state.

### Runtime components

- Backend API: `backend/app.py`
- Policy engine: `backend/policy_engine.py`
- Token vault: `backend/token_vault.py`
- Auth integration: `backend/auth.py`, `backend/routers/auth.py`
- Domain execution tools: `backend/mcp_tools.py`
- Frontend app (active): `frontend/src/`

## Tech Stack

### Backend

- FastAPI
- SQLAlchemy
- SQLite (default) or PostgreSQL
- Pydantic / pydantic-settings
- Auth0 integration support
- Google ADK and Google GenAI dependencies

### Frontend

- React 18
- Vite 5
- React Router 6
- Zustand
- Axios
- Tailwind CSS

## Repository Structure

```text
.
├── backend/                     # FastAPI API, policy engine, DB models, routers
│   ├── app.py                   # API entry point
│   ├── models.py                # SQLAlchemy models
│   ├── policy_engine.py         # Policy decisions + approval hooks
│   ├── mcp_tools.py             # Domain tool execution layer
│   ├── token_vault.py           # Scoped token management
│   └── routers/                 # API route groups
├── frontend/                    # Frontend workspace
│   ├── src/                     # Active React + Vite app
│   ├── app/, components/, ...   # Legacy/alternate UI artifacts (see caveats)
│   └── package.json
├── rag_agent/                   # RAG tooling and corpus operations
├── agent.py                     # Root ADK agent configuration
├── financial_tools.py           # Agent financial tools
├── support_tools.py             # Agent support tools
├── erp_tools.py                 # Agent ERP tools
├── docker-compose.yml
├── setup.ps1
└── setup.sh
```

## Quick Start

## 1) Prerequisites

- Python 3.10+
- Node.js 18+
- npm
- A Google Cloud account with billing enabled
- A Google Cloud project with the Vertex AI API enabled
- Appropriate access to create and manage Vertex AI resources
- Optional: Docker + Docker Compose

## 2) Setting Up Google Cloud Authentication

Before running the agent, you need to set up authentication with Google Cloud:

1. **Install Google Cloud CLI**:
   - Visit [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) for installation instructions for your OS

2. **Initialize the Google Cloud CLI**:
   ```bash
   gcloud init
   ```
   This will guide you through logging in and selecting your project.

3. **Set up Application Default Credentials**:
   ```bash
   gcloud auth application-default login
   ```
   This will open a browser window for authentication and store credentials in:
   `~/.config/gcloud/application_default_credentials.json`

4. **Verify Authentication**:
   ```bash
   gcloud auth list
   gcloud config list
   ```

5. **Enable Required APIs** (if not already enabled):
   ```bash
   gcloud services enable aiplatform.googleapis.com
  ```

## 3) Install dependencies

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

### macOS/Linux

```bash
chmod +x setup.sh
./setup.sh
```

These scripts:

- create backend virtual environment
- install backend requirements
- install frontend dependencies
- initialize the backend database

## 4) Start services (local development)

### Terminal A: backend

```bash
cd backend
# Windows PowerShell
.\venv\Scripts\Activate.ps1
# macOS/Linux
# source venv/bin/activate
python app.py
```

Backend default URL: `http://localhost:8000`

### Terminal B: frontend

```bash
cd frontend
npm run dev
```

Frontend default URL: `http://localhost:3000`

## 5) Verify health

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

## Environment Configuration

Backend settings are loaded from:

1. `backend/.env`
2. root `.env`

Use root `.env.example` as a base.

### Important backend variables

- `DEBUG`
- `DATABASE_URL`
- `SECRET_KEY`
- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `AUTH0_AUDIENCE`
- `AUTH0_REALM` (optional, for password-realm flows)
- `LOCAL_PASSWORD_LOGIN_FALLBACK` (default `True`)
- `AUTH0_TOKEN_VAULT_ENABLED` (default `True`)
- `AUTH0_TOKEN_VAULT_DEFAULT_CONNECTION`
- `AUTH0_TOKEN_VAULT_DEFAULT_SCOPES`

Frontend environment file: `frontend/.env.example`

- `VITE_API_URL=http://localhost:8000`

## Run with Docker

A compose file is provided:

```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
```

Declared services:

- `postgres`
- `backend`
- `frontend`

See caveats below regarding current frontend Dockerfile mismatch.

## Authentication and Access Model

Current login endpoint:

- `POST /api/auth/login`

Behavior:

- Primary mode: Auth0 credential exchange and profile lookup.
- Local fallback: if user already exists with `hashed_password` and `LOCAL_PASSWORD_LOGIN_FALLBACK=True`, local password verification is allowed.

Notes:

- Password length validation is enforced (minimum 8 characters).
- JWT is issued by backend and used as bearer token for protected routes.
- Admin-only endpoints exist for user listing and role updates.

## Policy and Approval Model

Policy engine location: `backend/policy_engine.py`

Default policy patterns include:

- `read_transactions` (financial): allow
- `create_transaction` (financial): require approval when amount is above threshold
- `process_refund` (support): require approval when amount is above threshold
- `create_purchase_order` (erp): require approval when amount is above threshold

Decision types:

- `allow`
- `require_approval`
- `deny`

Approval lifecycle:

1. Action evaluated as `require_approval`
2. Approval request stored in `approvals`
3. Reviewer approves/rejects
4. Action can proceed or remain blocked
5. Audit trail persists final state

## API Overview

Base URL: `http://localhost:8000`

### System and health

- `GET /`
- `GET /health`

### Auth (`/api/auth`)

- `POST /login`
- `POST /register`
- `GET /me`
- `GET /users`
- `PUT /users/{user_id}/role`

### Agent (`/api/agent`)

- `POST /execute`
- `GET /tools`
- `GET /tokens`
- `POST /token-request`
- `POST /session-memory/set`
- `GET /session-memory/{session_id}`

### Policy (`/api/policy`)

- `GET /list`
- `GET /check`
- `GET /dashboard`
- `GET /demo`

### Approval (`/api/approval`)

- `POST /request`
- `GET /queue`
- `GET /{approval_id}`
- `POST /{approval_id}/approve`
- `POST /{approval_id}/reject`
- `GET /user/{user_id}/pending`

### Audit (`/api/audit`)

- `GET /logs`
- `GET /logs/summary`
- `GET /logs/by-system`

### Financial (`/api/financial`)

- Customers, accounts, transactions, refunds, user summary endpoints
- Includes `GET /my/transactions` and `GET /my/summary`

### Support (`/api/support`)

- Ticket lifecycle endpoints
- Chat bootstrap and admin conversation endpoints
- Approval decision hooks in support chat flows

### ERP (`/api/erp`)

- Purchase order create/read/update/status endpoints
- Includes `GET /my/purchase-orders` and `GET /my/summary`

### Session (`/api/session`)

- Create, get, list, update, context/history append, delete

### Knowledge Base (`/api/knowledge-base`)

- Upload/list/get/delete documents
- Stats and sync endpoints

### Auth0 Token Vault (`/api/token-vault`)

- `GET /requirements`
- `POST /exchange`

## Data Model Overview

Primary entities defined in `backend/models.py`:

- Identity and access:
  - `User`
  - `Token`
  - `Policy`
  - `Approval`
  - `AuditLog`
- Session and knowledge:
  - `Session`
  - `KnowledgeBaseDocument`
- Financial domain:
  - `Customer`
  - `Account`
  - `Transaction`
  - `Refund`
- Support domain:
  - `SupportTicket`
  - `Message`
- ERP domain:
  - `PurchaseOrder`

## Operational Flows

### Example 1: low-risk read

1. User requests transaction read.
2. Policy returns `allow`.
3. Vault token issued with read scope.
4. Tool executes and response returns immediately.

### Example 2: high-risk refund

1. User requests refund above policy threshold.
2. Policy returns `require_approval`.
3. Approval request enters queue.
4. Approver resolves request.
5. Action executes if approved.

### Example 3: blocked action

1. No matching policy or explicit deny rule.
2. Policy returns `deny`.
3. Action not executed.
4. Audit entry records denial reason.

## Troubleshooting

### Backend will not start

- Confirm Python environment is activated.
- Verify `SECRET_KEY` is set.
- Validate `DATABASE_URL` format.

### Login fails

- If using Auth0, verify Auth0 env variables.
- If using local fallback, ensure user exists and has `hashed_password`.
- Use `backend/hash_password_cli.py` to backfill missing password hashes if needed.

Example:

```bash
cd backend
python hash_password_cli.py --yes --password 12345678
```

### Frontend cannot reach API

- Confirm backend is running on `http://localhost:8000`.
- Ensure `frontend/.env` has correct `VITE_API_URL`.
- Restart Vite after env changes.

### Port conflicts

- Backend default: 8000
- Frontend default: 3000

Adjust process usage or stop conflicting services.

## Known Repository Caveats

- Frontend contains both active Vite/React code (`frontend/src`) and legacy/alternate Next.js-era artifacts (`frontend/app`, `.next`, related config files).
- `frontend/Dockerfile` currently uses Next.js build/runtime assumptions (`.next`, `npm start`) while `frontend/package.json` scripts are Vite-based.
- `backend/pyproject.toml` metadata does not currently mirror the runtime package/requirements set used by `requirements.txt`.
- `backend/hash_password_cli.py` contains trailing unrelated code after the CLI section; review before production hardening.

These do not prevent local development with the documented `python app.py` and `npm run dev` flow, but should be addressed for production readiness.

## Additional Documentation

Project includes detailed supplemental docs:

- `ARCHITECTURE.md`

## License

MIT License. See `LICENSE`.
