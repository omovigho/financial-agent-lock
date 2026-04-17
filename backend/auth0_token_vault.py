"""Auth0 Token Vault helpers for external provider token exchange."""
from typing import Any, Optional

from auth0 import Auth0Error
from auth0.authentication.get_token import GetToken

from config import settings

SUBJECT_TYPE_ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"
REQUESTED_TOKEN_TYPE_FEDERATED_ACCESS_TOKEN = (
    "http://auth0.com/oauth/token-type/federated-connection-access-token"
)


class Auth0TokenVaultService:
    """Service for exchanging Auth0 user access tokens for provider access tokens."""

    def __init__(self) -> None:
        self.client_id = settings.token_vault_exchange_client_id
        self.client_secret = settings.token_vault_exchange_client_secret
        self.domain = settings.auth0_domain

        if not self.domain:
            raise ValueError("AUTH0_DOMAIN is required for Token Vault")
        if not self.client_id:
            raise ValueError(
                "AUTH0_TOKEN_VAULT_CLIENT_ID (or AUTH0_CLIENT_ID) is required"
            )
        if not self.client_secret:
            raise ValueError(
                "AUTH0_TOKEN_VAULT_CLIENT_SECRET (or AUTH0_CLIENT_SECRET) is required"
            )

        self._token_client = GetToken(
            domain=self.domain,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

    @staticmethod
    def requirements() -> dict[str, Any]:
        """Return required Token Vault setup values and whether they're configured."""
        return {
            "tenant": {
                "auth0_domain": {
                    "required": True,
                    "configured": bool(settings.auth0_domain),
                    "source": "AUTH0_DOMAIN",
                },
            },
            "token_exchange_client": {
                "auth0_token_vault_client_id": {
                    "required": True,
                    "configured": bool(settings.token_vault_exchange_client_id),
                    "source": "AUTH0_TOKEN_VAULT_CLIENT_ID or AUTH0_CLIENT_ID",
                },
                "auth0_token_vault_client_secret": {
                    "required": True,
                    "configured": bool(settings.token_vault_exchange_client_secret),
                    "source": "AUTH0_TOKEN_VAULT_CLIENT_SECRET or AUTH0_CLIENT_SECRET",
                },
            },
            "runtime": {
                "connection": {
                    "required": True,
                    "default": settings.auth0_token_vault_default_connection,
                    "example": "google-oauth2",
                },
                "required_scopes": {
                    "required": True,
                    "default": settings.token_vault_default_scopes_list,
                },
                "subject_token": {
                    "required": True,
                    "description": "Auth0 user access token received by backend API",
                    "subject_token_type": SUBJECT_TYPE_ACCESS_TOKEN,
                },
            },
        }

    def exchange_access_token(
        self,
        subject_token: str,
        connection: str,
        required_scopes: Optional[list[str]] = None,
        login_hint: Optional[str] = None,
    ) -> dict[str, Any]:
        """Exchange Auth0 user access token for a provider token from Token Vault."""
        if not subject_token:
            raise ValueError("subject_token is required")
        if not connection:
            raise ValueError("connection is required")

        try:
            response = self._token_client.access_token_for_connection(
                subject_token_type=SUBJECT_TYPE_ACCESS_TOKEN,
                subject_token=subject_token,
                requested_token_type=REQUESTED_TOKEN_TYPE_FEDERATED_ACCESS_TOKEN,
                connection=connection,
                login_hint=login_hint,
            )
        except Auth0Error as err:
            message = getattr(err, "message", "Auth0 token exchange failed")
            raise ValueError(message) from err

        granted_scopes = [s for s in str(response.get("scope", "")).split(" ") if s]

        if required_scopes:
            missing = [scope for scope in required_scopes if scope not in granted_scopes]
            if missing:
                raise ValueError(
                    "Token Vault exchange succeeded but required scopes are missing: "
                    + ", ".join(missing)
                )

        return {
            "access_token": response.get("access_token"),
            "scope": granted_scopes,
            "expires_in": response.get("expires_in"),
            "token_type": response.get("token_type", "Bearer"),
            "issued_token_type": response.get("issued_token_type"),
            "connection": connection,
        }
