"""Auth API routes."""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from auth import AuthHandler, get_current_user
from database import get_db
from models import User
from config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str
    user: dict
    auth0_access_token: Optional[str] = None
    auth0_refresh_token: Optional[str] = None


class UserResponse(BaseModel):
    """User response model."""
    id: int
    email: str
    name: str
    auth0_id: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    email = str(request.email)
    user = db.query(User).filter(User.email == email).first()

    # Token Vault docs assume Auth0-issued tokens (typically via PKCE), but this
    # fallback keeps existing local users working when Auth0 password grants are disabled.
    if (
        settings.local_password_login_fallback
        and user
        and user.hashed_password
        and AuthHandler.verify_password(request.password, user.hashed_password)
    ):
        access_token = AuthHandler.create_access_token(
            user_id=user.id,
            email=user.email,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "auth0_access_token": None,
            "auth0_refresh_token": None,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "auth0_id": user.auth0_id,
                "role": user.role,
            }
        }

    try:
        auth_data = await AuthHandler.auth0_login(email, request.password)
    except HTTPException as exc:
        if (
            settings.local_password_login_fallback
            and user
            and user.hashed_password
            and exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            and "not authorized for password login" in str(exc.detail).lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            ) from exc
        raise
    
    if not auth_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    password_hash = AuthHandler.get_password_hash(request.password)

    # Check if user exists, create if not
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        user = User(
            email=email,
            hashed_password=password_hash,
            auth0_id=auth_data["auth0_id"],
            name=auth_data["name"],
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.hashed_password:
        user.hashed_password = password_hash
        db.commit()
        db.refresh(user)
    
    # Create JWT token
    access_token = AuthHandler.create_access_token(
        user_id=user.id,
        email=user.email,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "auth0_access_token": auth_data.get("auth0_access_token"),
        "auth0_refresh_token": auth_data.get("auth0_refresh_token"),
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "auth0_id": user.auth0_id,
            "role": user.role,
        }
    }


@router.post("/register")
async def register(request: LoginRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    if not settings.allow_mock_auth:
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Direct registration is disabled. Use your identity provider signup flow."
        )

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == str(request.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already registered"
        )
    
    # Create new user
    auth_data = AuthHandler.mock_auth0_login(str(request.email), request.password)
    
    user = User(
        email=str(request.email),
        hashed_password=AuthHandler.get_password_hash(request.password),
        auth0_id=auth_data["auth0_id"],
        name=auth_data["name"],
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    access_token = AuthHandler.create_access_token(
        user_id=user.id,
        email=user.email,
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "auth0_id": current_user.auth0_id,
        "role": current_user.role,
    }


def get_admin_user(current_user: User = Depends(get_current_user)):
    """Dependency to ensure user is admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


class RoleUpdateRequest(BaseModel):
    """Request to update user role."""
    user_id: int
    role: str


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    request: RoleUpdateRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Update user role (admin only)."""
    if request.role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Role must be "user" or "admin"'
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.role = request.role
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "auth0_id": user.auth0_id,
        "role": user.role,
    }


@router.get("/users", response_model=dict)
async def list_users(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List all users (admin only)."""
    users = db.query(User).all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "count": len(users),
    }
