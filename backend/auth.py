"""Authentication module for Auth0 integration."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
import bcrypt
import logging
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from config import settings
from models import User
from database import get_db

BCRYPT_ROUNDS = 12
logger = logging.getLogger(__name__)


def _normalize_password(password: str) -> bytes:
    """Normalize password for bcrypt's 72-byte input limit."""
    return password.encode("utf-8")[:72]

# JWT Security
security = HTTPBearer()


class AuthHandler:
    """Handle authentication and token management."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password."""
        if not hashed_password:
            return False

        try:
            return bcrypt.checkpw(
                _normalize_password(plain_password),
                hashed_password.encode("utf-8")
            )
        except ValueError:
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash password."""
        hashed = bcrypt.hashpw(
            _normalize_password(password),
            bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        )
        return hashed.decode("utf-8")
    
    @staticmethod
    def create_access_token(
        user_id: int,
        email: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create JWT access token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.access_token_expire_minutes
            )
        
        to_encode = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm]
            )
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            return {"user_id": int(user_id), "email": email}
        
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    @staticmethod
    async def auth0_login(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user against Auth0 and return normalized profile data."""
        required_values = {
            "AUTH0_DOMAIN": settings.auth0_domain,
            "AUTH0_CLIENT_ID": settings.auth0_client_id,
            "AUTH0_CLIENT_SECRET": settings.auth0_client_secret,
            "AUTH0_AUDIENCE": settings.auth0_audience,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Auth0 is not configured. Missing: {', '.join(missing)}"
            )

        token_url = f"https://{settings.auth0_domain}/oauth/token"
        userinfo_url = f"https://{settings.auth0_domain}/userinfo"

        standard_payload = {
            "grant_type": "password",
            "username": email,
            "password": password,
            "client_id": settings.auth0_client_id,
            "client_secret": settings.auth0_client_secret,
            "audience": settings.auth0_audience,
            "scope": (
                "openid profile email offline_access"
                if settings.auth0_request_offline_access
                else "openid profile email"
            ),
        }
        payload_candidates = []
        if settings.auth0_realm:
            realm_payload = dict(standard_payload)
            realm_payload["grant_type"] = "http://auth0.com/oauth/grant-type/password-realm"
            realm_payload["realm"] = settings.auth0_realm
            payload_candidates.append(("password-realm", realm_payload))

        payload_candidates.append(("password", standard_payload))

        try:
            async with httpx.AsyncClient(timeout=settings.auth0_request_timeout_seconds) as client:
                auth0_access_token: Optional[str] = None
                auth0_refresh_token: Optional[str] = None

                for grant_name, payload in payload_candidates:
                    token_response = await client.post(token_url, json=payload)

                    if token_response.status_code in (400, 401, 403):
                        error_body: Dict[str, Any] = {}
                        try:
                            error_body = token_response.json()
                        except ValueError:
                            error_body = {}

                        error_code = str(error_body.get("error", ""))
                        error_description = str(error_body.get("error_description", ""))
                        description_lower = error_description.lower()

                        logger.warning(
                            "Auth0 token rejected request: grant=%s status=%s error=%s description=%s",
                            grant_name,
                            token_response.status_code,
                            error_code,
                            error_description,
                        )

                        if (
                            grant_name == "password-realm"
                            and error_code == "unauthorized_client"
                        ):
                            logger.warning(
                                "Auth0 password-realm grant is not enabled for this client; falling back to password grant"
                            )
                            continue

                        if error_code == "invalid_grant":
                            return None

                        if error_code == "mfa_required":
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="MFA is required and must be completed via the identity provider flow"
                            )

                        if error_code == "unauthorized_client":
                            raise HTTPException(
                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=(
                                    "Auth0 client is not authorized for password login. "
                                    "Enable Password/Password Realm grant types for this Auth0 application."
                                )
                            )

                        if "default directory" in description_lower or "connection" in description_lower:
                            raise HTTPException(
                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=(
                                    "Auth0 needs a database connection realm for password login. "
                                    "Set AUTH0_REALM to your Auth0 DB connection name "
                                    "(for example Username-Password-Authentication)."
                                )
                            )

                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid credentials"
                        )

                    if token_response.status_code >= 500:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Auth0 authentication service is unavailable"
                        )

                    token_response.raise_for_status()
                    token_data = token_response.json()
                    auth0_access_token = token_data.get("access_token")
                    auth0_refresh_token = token_data.get("refresh_token")
                    if not auth0_access_token:
                        return None
                    break

                if not auth0_access_token:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Auth0 did not provide an access token"
                    )

                userinfo_response = await client.get(
                    userinfo_url,
                    headers={"Authorization": f"Bearer {auth0_access_token}"},
                )

                if userinfo_response.status_code >= 500:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Auth0 profile service is unavailable"
                    )

                userinfo_response.raise_for_status()
                profile = userinfo_response.json()

                auth0_id = profile.get("sub")
                if not auth0_id:
                    return None

                return {
                    "email": profile.get("email", email),
                    "auth0_id": auth0_id,
                    "name": profile.get("name") or profile.get("nickname") or email.split("@")[0].title(),
                    "auth0_access_token": auth0_access_token,
                    "auth0_refresh_token": auth0_refresh_token,
                }

        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Auth0"
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 401, 403):
                detail = "Invalid credentials"
                response_json = exc.response.json() if exc.response.content else {}
                if response_json.get("error") == "mfa_required":
                    detail = "MFA is required and must be completed via the identity provider flow"
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=detail
                ) from exc

            if exc.response.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication provider rate limit reached"
                ) from exc

            if exc.response.status_code >= 500:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication provider error"
                ) from exc

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unexpected response from authentication provider"
            ) from exc
    
    @staticmethod
    def mock_auth0_login(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Mock Auth0 login (in production, call Auth0 API)."""
        if not settings.allow_mock_auth:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mock authentication is disabled"
            )

        # For local demo purposes only, accept any email/password combination
        return {
            "email": email,
            "auth0_id": f"auth0|{email.split('@')[0]}",
            "name": email.split('@')[0].title(),
        }


async def get_current_user(
    credentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    try:
        token_data = AuthHandler.verify_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user
