"""Auth0 Token Vault routes."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import get_current_user
from auth0_token_vault import Auth0TokenVaultService
from config import settings
from models import User

router = APIRouter(prefix="/api/token-vault", tags=["token-vault"])


class TokenVaultExchangeRequest(BaseModel):
    """Request model for Token Vault access token exchange."""

    subject_token: str = Field(
        ...,
        description="Auth0 user access token to exchange",
        min_length=16,
    )
    connection: Optional[str] = Field(
        default=None,
        description="Auth0 connection name (example: google-oauth2)",
    )
    required_scopes: Optional[list[str]] = Field(
        default=None,
        description="Scopes that must be present in the exchanged token",
    )
    login_hint: Optional[str] = Field(
        default=None,
        description="Optional account selector if user linked multiple identities",
    )


@router.get("/requirements")
async def get_token_vault_requirements(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get Auth0 Token Vault setup requirements and current configuration state."""
    return {
        "enabled": settings.auth0_token_vault_enabled,
        "requirements": Auth0TokenVaultService.requirements(),
        "current_user": {
            "id": current_user.id,
            "auth0_id": current_user.auth0_id,
            "email": current_user.email,
        },
    }


@router.post("/exchange")
async def exchange_token_vault_access_token(
    request: TokenVaultExchangeRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Exchange an Auth0 user access token for a provider access token from Token Vault."""
    if not settings.auth0_token_vault_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth0 Token Vault is disabled",
        )

    connection = request.connection or settings.auth0_token_vault_default_connection
    required_scopes = request.required_scopes or settings.token_vault_default_scopes_list

    try:
        token_vault = Auth0TokenVaultService()
        result = token_vault.exchange_access_token(
            subject_token=request.subject_token,
            connection=connection,
            required_scopes=required_scopes,
            login_hint=request.login_hint,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    return {
        "status": "success",
        "connection": connection,
        "required_scopes": required_scopes,
        "token": result,
        "user": {
            "id": current_user.id,
            "auth0_id": current_user.auth0_id,
        },
    }
