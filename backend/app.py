"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from config import settings
from database import init_db
from routers import (
    auth,
    agent,
    policy,
    audit_logs,
    session,
    knowledge_base,
    approval,
    financial,
    support,
    erp,
    token_vault,
)

logger = logging.getLogger(__name__)

# Initialize database
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    # Startup
    logger.info("Starting Agent-Lock application...")
    init_db()
    yield
    # Shutdown
    logger.info("Shutting down Agent-Lock application...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Secure AI Financial Operations Platform with Policy Enforcement",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(policy.router)
app.include_router(audit_logs.router)
app.include_router(session.router)
app.include_router(knowledge_base.router)
app.include_router(approval.router)
app.include_router(financial.router)
app.include_router(support.router)
app.include_router(erp.router)
app.include_router(token_vault.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "endpoints": {
            "auth": "/api/auth",
            "agent": "/api/agent",
            "policy": "/api/policy",
            "approval": "/api/approval",
            "audit": "/api/audit",
            "token_vault": "/api/token-vault",
            "docs": "/docs",
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
