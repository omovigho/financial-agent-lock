"""Session management router for multi-user context handling."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import uuid
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as SQLSession

from database import get_db
from models import Session, User
from routers.auth import get_current_user

router = APIRouter(prefix="/api/session", tags=["sessions"])


class SessionCreate(BaseModel):
    """Session creation request."""
    context: Dict[str, Any] = {}
    corpus_name: str = "agent-lock"


class SessionResponse(BaseModel):
    """Session response model."""
    session_id: str
    user_id: int
    context: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    current_corpus: str
    is_active: bool
    created_at: datetime
    last_activity_at: datetime
    expires_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class SessionUpdate(BaseModel):
    """Session update request."""
    context: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    current_corpus: Optional[str] = None
    is_active: Optional[bool] = None


def generate_session_id(user_id: int) -> str:
    """Generate unique session ID."""
    timestamp = datetime.utcnow().isoformat()
    unique_part = str(uuid.uuid4())[:8]
    return f"user_{user_id}_{timestamp}_{unique_part}"


@router.post("/create", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Create a new user session for context management.
    
    Args:
        session_data: Session initialization data
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Created session details
    """
    # Generate unique session ID
    session_id = generate_session_id(current_user.id)
    
    # Set expiration (e.g., 24 hours from now)
    expires_at = datetime.utcnow() + timedelta(days=1)
    
    # Create session
    db_session = Session(
        session_id=session_id,
        user_id=current_user.id,
        context=session_data.context or {},
        conversation_history=[],
        current_corpus=session_data.corpus_name,
        is_active=True,
        expires_at=expires_at,
    )
    
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    return SessionResponse.from_orm(db_session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Get session details.
    
    Args:
        session_id: Session identifier
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Session details if authorized
    """
    # Get session
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Check authorization - user can only access their own sessions (admin can access all)
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    # Check if session is expired
    if session.expires_at and datetime.utcnow() > session.expires_at:
        session.is_active = False
        db.commit()
    
    # Update last activity
    session.last_activity_at = datetime.utcnow()
    db.commit()
    
    return SessionResponse.from_orm(session)


@router.get("/user/list", response_model=List[SessionResponse])
async def list_user_sessions(
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SessionResponse]:
    """
    List user's sessions.
    
    Args:
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        List of user's sessions
    """
    sessions = db.query(Session).filter(
        Session.user_id == current_user.id
    ).order_by(Session.created_at.desc()).all()
    
    return [SessionResponse.from_orm(s) for s in sessions]


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    session_update: SessionUpdate,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Update session context.
    
    Args:
        session_id: Session identifier
        session_update: Updated session data
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Updated session details
    """
    # Get session
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Check authorization
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this session"
        )
    
    # Update fields if provided
    if session_update.context is not None:
        session.context = session_update.context
    
    if session_update.conversation_history is not None:
        # Keep only latest N interactions (e.g., last 20)
        max_history = 20
        history = session_update.conversation_history[-max_history:]
        session.conversation_history = history
    
    if session_update.current_corpus is not None:
        session.current_corpus = session_update.current_corpus
    
    if session_update.is_active is not None:
        session.is_active = session_update.is_active
    
    # Update activity timestamp
    session.last_activity_at = datetime.utcnow()
    
    db.commit()
    db.refresh(session)
    
    return SessionResponse.from_orm(session)


@router.post("/{session_id}/context", response_model=Dict[str, Any])
async def update_session_context(
    session_id: str,
    context_data: Dict[str, Any],
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Add/update session context data.
    
    Args:
        session_id: Session identifier
        context_data: Context data to merge
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Updated context
    """
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    # Merge context data
    session.context.update(context_data)
    session.last_activity_at = datetime.utcnow()
    
    db.commit()
    db.refresh(session)
    
    return session.context


@router.post("/{session_id}/history", response_model=List[Dict[str, Any]])
async def add_to_conversation_history(
    session_id: str,
    interaction: Dict[str, Any],
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Add interaction to conversation history.
    
    Args:
        session_id: Session identifier
        interaction: Conversation interaction to add
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Updated conversation history
    """
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    # Add timestamp if not present
    if "timestamp" not in interaction:
        interaction["timestamp"] = datetime.utcnow().isoformat()
    
    # Add to history, keep only latest N
    max_history = 20
    history = session.conversation_history or []
    history.append(interaction)
    session.conversation_history = history[-max_history:]
    
    session.last_activity_at = datetime.utcnow()
    
    db.commit()
    db.refresh(session)
    
    return session.conversation_history


@router.delete("/{session_id}", response_model=Dict[str, str])
async def delete_session(
    session_id: str,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Delete a session.
    
    Args:
        session_id: Session identifier
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Deletion confirmation
    """
    session = db.query(Session).filter(Session.session_id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    db.delete(session)
    db.commit()
    
    return {"message": "Session deleted successfully"}
