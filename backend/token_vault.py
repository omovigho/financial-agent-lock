"""Token Vault implementation for secure token management."""
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
import secrets
from sqlalchemy.orm import Session
from models import Token, User
from config import settings


@dataclass
class VaultToken:
    """Represents a token from the vault."""
    token_id: str
    scope: str
    system: str
    expires_at: datetime
    created_at: datetime


class TokenVault:
    """Secure token vault for managing delegated access."""
    
    def __init__(self, db: Session):
        """Initialize vault with database session."""
        self.db = db
        self.vault_storage = {}  # In-memory storage for demo
        self._load_vault()
    
    def _load_vault(self):
        """Load existing tokens from database."""
        tokens = self.db.query(Token).filter(Token.is_active == True).all()
        for token in tokens:
            if token.expires_at > datetime.utcnow():
                self.vault_storage[token.token_id] = {
                    "scope": token.scope,
                    "system": token.system,
                    "expires_at": token.expires_at.isoformat(),
                }
    
    def create_token(
        self,
        user_id: int,
        scope: str,
        system: str,
        ttl_seconds: Optional[int] = None,
    ) -> VaultToken:
        """
        Create a scoped, temporary token for delegated access.
        
        Args:
            user_id: User requesting the token
            scope: Token scope (e.g., "read:transactions", "write:refund")
            system: System the token grants access to
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            VaultToken with token_id and metadata
        """
        ttl = ttl_seconds or settings.token_vault_ttl_seconds
        token_id = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        created_at = datetime.utcnow()
        
        # Store in vault
        self.vault_storage[token_id] = {
            "scope": scope,
            "system": system,
            "expires_at": expires_at.isoformat(),
            "user_id": user_id,
        }
        
        # Record in database
        db_token = Token(
            user_id=user_id,
            token_id=token_id,
            scope=scope,
            system=system,
            expires_at=expires_at,
        )
        self.db.add(db_token)
        self.db.commit()
        
        return VaultToken(
            token_id=token_id,
            scope=scope,
            system=system,
            expires_at=expires_at,
            created_at=created_at,
        )
    
    def verify_token(self, token_id: str, required_scope: str) -> bool:
        """
        Verify a token is valid and has required scope.
        
        Args:
            token_id: Token to verify
            required_scope: Required scope
            
        Returns:
            True if valid, False otherwise
        """
        if token_id not in self.vault_storage:
            return False
        
        token_data = self.vault_storage[token_id]
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        
        # Check expiration
        if expires_at <= datetime.utcnow():
            self._revoke_token(token_id)
            return False
        
        # Check scope
        token_scope = token_data["scope"]
        if not self._scope_matches(token_scope, required_scope):
            return False
        
        return True
    
    def get_token_metadata(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a token."""
        if token_id in self.vault_storage:
            return self.vault_storage[token_id]
        return None
    
    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token."""
        return self._revoke_token(token_id)
    
    def _revoke_token(self, token_id: str) -> bool:
        """Internal token revocation."""
        if token_id in self.vault_storage:
            del self.vault_storage[token_id]
        
        token = self.db.query(Token).filter(Token.token_id == token_id).first()
        if token:
            token.is_active = False
            self.db.commit()
            return True
        return False
    
    def _scope_matches(self, token_scope: str, required_scope: str) -> bool:
        """Check if token scope matches required scope."""
        # Simple scope matching: "read:*" matches any read scope
        if token_scope.endswith("*"):
            prefix = token_scope[:-1]
            return required_scope.startswith(prefix)
        return token_scope == required_scope
    
    def list_user_tokens(self, user_id: int) -> list:
        """List all active tokens for a user."""
        tokens = self.db.query(Token).filter(
            Token.user_id == user_id,
            Token.is_active == True
        ).all()
        return [
            {
                "token_id": t.token_id,
                "scope": t.scope,
                "system": t.system,
                "expires_at": t.expires_at.isoformat(),
                "created_at": t.created_at.isoformat(),
            }
            for t in tokens
        ]
