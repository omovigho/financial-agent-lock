"""
Agent-Lock: Secure AI Financial Operations Platform

A production-grade full-stack application demonstrating how AI agents can safely operate
across financial, customer support, and ERP systems using Auth0, Token Vault, and 
policy-based guardrails.

Core Components:
- Google ADK Agent for orchestration
- Policy Engine for access control
- Token Vault for scoped delegation
- FastAPI backend with Auth0 integration
- Next.js dashboard frontend
"""

from . import agent

__version__ = "1.0.0"
__author__ = "Agent-Lock Team"
