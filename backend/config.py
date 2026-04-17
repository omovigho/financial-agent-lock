"""Configuration module for Agent-Lock backend."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


def _parse_csv(value: str) -> list[str]:
    """Parse comma-separated env values into a clean list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    app_name: str = "Agent-Lock"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./agent_lock.db"
    )
    
    # Auth0
    auth0_domain: str = os.getenv("AUTH0_DOMAIN", "")
    auth0_client_id: str = os.getenv("AUTH0_CLIENT_ID", "")
    auth0_client_secret: str = os.getenv("AUTH0_CLIENT_SECRET", "")
    auth0_audience: str = os.getenv("AUTH0_AUDIENCE", "")
    auth0_realm: str = os.getenv("AUTH0_REALM", "")
    auth0_request_offline_access: bool = os.getenv(
        "AUTH0_REQUEST_OFFLINE_ACCESS", "False"
    ).lower() == "true"
    auth0_request_timeout_seconds: float = float(
        os.getenv("AUTH0_REQUEST_TIMEOUT_SECONDS", "10")
    )

    # Auth0 Token Vault (access token exchange)
    auth0_token_vault_enabled: bool = os.getenv(
        "AUTH0_TOKEN_VAULT_ENABLED", "True"
    ).lower() == "true"
    auth0_token_vault_client_id: str = os.getenv(
        "AUTH0_TOKEN_VAULT_CLIENT_ID", ""
    )
    auth0_token_vault_client_secret: str = os.getenv(
        "AUTH0_TOKEN_VAULT_CLIENT_SECRET", ""
    )
    auth0_token_vault_default_connection: str = os.getenv(
        "AUTH0_TOKEN_VAULT_DEFAULT_CONNECTION", "google-oauth2"
    )
    auth0_token_vault_default_scopes: str = os.getenv(
        "AUTH0_TOKEN_VAULT_DEFAULT_SCOPES",
        "openid,https://www.googleapis.com/auth/calendar.events",
    )

    # Development guardrail (must stay False in production)
    #allow_mock_auth: bool = os.getenv("ALLOW_MOCK_AUTH", "False").lower() == "true"
    local_password_login_fallback: bool = os.getenv(
        "LOCAL_PASSWORD_LOGIN_FALLBACK", "True"
    ).lower() == "true"
    
    # JWT
    secret_key: str = os.getenv("SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Token Vault
    token_vault_enabled: bool = True
    token_vault_ttl_seconds: int = 3600  # 1 hour
    
    # CORS
    cors_origins: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Google ADK
    google_genai_use_vertexai: bool = os.getenv(
        "GOOGLE_GENAI_USE_VERTEXAI", "True"
    ).lower() in {"1", "true", "yes"}
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    
    class Config:
        env_file = (
            str(BACKEND_DIR / ".env"),
            str(PROJECT_ROOT_DIR / ".env"),
        )
        case_sensitive = False
        extra = "ignore"

    @property
    def token_vault_exchange_client_id(self) -> str:
        """Client ID used for Token Vault token exchange (Custom API Client preferred)."""
        return self.auth0_token_vault_client_id or self.auth0_client_id

    @property
    def token_vault_exchange_client_secret(self) -> str:
        """Client secret used for Token Vault token exchange (Custom API Client preferred)."""
        return self.auth0_token_vault_client_secret or self.auth0_client_secret

    @property
    def token_vault_default_scopes_list(self) -> list[str]:
        """Default Token Vault scopes as a normalized list."""
        return _parse_csv(self.auth0_token_vault_default_scopes)


settings = Settings()
