"""Knowledge Base document management router."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import os
import sys
import logging
import aiofiles

# Add parent directory to path to import rag_agent from root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session as SQLSession

from database import get_db
from models import KnowledgeBaseDocument, User
from routers.auth import get_current_user, get_admin_user
from rag_agent.tools.upload_document import upload_document
from rag_agent.tools.get_corpus_info import get_corpus_info
from rag_agent.tools.delete_document import delete_document as rag_delete_document
from cache_utils import get_cache, CacheKey

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

# Configuration
import tempfile

# Use the platform temporary directory to avoid mixed-path issues on Windows
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "agent-lock-uploads")  # Temporary directory for uploads
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.doc', '.pptx', '.xlsx', '.csv', '.html', '.json', '.md'}


class DocumentResponse(BaseModel):
    """Knowledge base document response."""
    id: int
    doc_id: str
    filename: str
    uploaded_by: Optional[int]
    file_extension: str
    file_size_bytes: int
    corpus_id: str
    status: str
    embedded_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Document listing response."""
    total: int
    documents: List[DocumentResponse]


class DocumentDeleteRequest(BaseModel):
    """Document deletion request."""
    confirm: bool = False
    reason: Optional[str] = None
    doc_id: Optional[str] = None
    filename: Optional[str] = None


async def ensure_upload_dir():
    """Ensure upload directory exists."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def validate_file(filename: str, file_size: int) -> None:
    """
    Validate file before upload.
    
    Args:
        filename: File name to validate
        file_size: File size in bytes
        
    Raises:
        HTTPException: If validation fails
    """
    # Check file extension
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed ({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"
        )


def _normalize_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetimes for consistent UTC comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_rag_timestamp(value: str) -> Optional[datetime]:
    """Parse RAG timestamp strings into timezone-aware UTC datetimes."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _normalize_utc(parsed)
    except Exception:
        return None


def resolve_rag_file_candidates(
    filename: Optional[str] = None,
    source_uri: Optional[str] = None,
    expected_doc_id: Optional[str] = None,
    db_created_at: Optional[datetime] = None,
) -> List[str]:
    """Return ordered candidate RAG file IDs using doc_id + filename/source metadata."""
    candidates: List[str] = []

    def add_candidate(file_id: Optional[str]) -> None:
        if file_id and file_id not in candidates:
            candidates.append(file_id)

    try:
        corpus_info = get_corpus_info(corpus_name="agent-lock", tool_context=None)
        if not isinstance(corpus_info, dict) or corpus_info.get("status") == "error":
            return candidates

        files = corpus_info.get("files", []) or []

        # 1) If expected id already exists in corpus, use it.
        if expected_doc_id:
            for rag_file in files:
                if rag_file.get("file_id") == expected_doc_id:
                    add_candidate(expected_doc_id)
                    break

        # 2) Strong match by source URI.
        if source_uri:
            for rag_file in files:
                if rag_file.get("source_uri") == source_uri:
                    add_candidate(rag_file.get("file_id"))

        # 3) Filename matches (single match direct, multi-match ordered by nearest create_time).
        if filename:
            filename_matches: List[Dict[str, Any]] = [
                rag_file
                for rag_file in files
                if rag_file.get("display_name") == filename and rag_file.get("file_id")
            ]
            if len(filename_matches) == 1:
                add_candidate(filename_matches[0].get("file_id"))
            elif len(filename_matches) > 1:
                normalized_db_created_at = _normalize_utc(db_created_at)
                if normalized_db_created_at:
                    filename_matches.sort(
                        key=lambda rag_file: abs(
                            (_parse_rag_timestamp(rag_file.get("create_time", "")) or normalized_db_created_at)
                            - normalized_db_created_at
                        ).total_seconds()
                    )
                for rag_file in filename_matches:
                    add_candidate(rag_file.get("file_id"))

        # 4) If source URI exists in corpus and ends with filename, use it.
        if filename:
            uri_suffix_matches: List[str] = [
                rag_file.get("file_id")
                for rag_file in files
                if rag_file.get("source_uri") and rag_file.get("source_uri", "").endswith(f"/{filename}")
                and rag_file.get("file_id")
            ]
            for file_id in uri_suffix_matches:
                add_candidate(file_id)

    except Exception:
        logger.exception("Failed to resolve RAG file ID for filename=%s, source_uri=%s", filename, source_uri)

    return candidates


def resolve_rag_file_id(
    filename: Optional[str] = None,
    source_uri: Optional[str] = None,
    expected_doc_id: Optional[str] = None,
    db_created_at: Optional[datetime] = None,
) -> Optional[str]:
    """Resolve a single best RAG file ID candidate."""
    candidates = resolve_rag_file_candidates(
        filename=filename,
        source_uri=source_uri,
        expected_doc_id=expected_doc_id,
        db_created_at=db_created_at,
    )
    return candidates[0] if candidates else None


@router.post("/upload", response_model=DocumentResponse)
async def upload_document_handler(
    file: UploadFile = File(...),
    db: SQLSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
) -> DocumentResponse:
    """
    Upload a document to the knowledge base.
    
    Args:
        file: File to upload
        db: Database connection
        admin_user: Authenticated admin user (admin only)
    
    Returns:
        Uploaded document details
    """
    try:
        # Read file content into memory (no local persistence)
        content = await file.read()
        file_size = len(content)

        # Validate file
        validate_file(file.filename, file_size)

        logger.info(f"Received upload {file.filename} ({file_size} bytes)")

        # Upload to RAG corpus using the tool (upload from bytes)
        upload_result = upload_document(file_bytes=content, filename=file.filename, tool_context=None)
        logger.info(f"RAG upload result: %s", upload_result)

        if not isinstance(upload_result, dict) or upload_result.get("status") == "error":
            message = (
                upload_result.get('message') if isinstance(upload_result, dict) else 'Unexpected upload result'
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload document: {message}"
            )

        # Get the source URI from upload result (GCS path)
        source_uri = upload_result.get("file_uri") if isinstance(upload_result, dict) else None
        
        # Prefer the RAG-assigned file_id if available, otherwise fall back to a
        # deterministic ID derived from the GCS source URI or filename.
        file_entries = upload_result.get('file_entries') if isinstance(upload_result, dict) else None
        import hashlib
        if file_entries and isinstance(file_entries, list) and file_entries[0].get('file_id'):
            doc_id = file_entries[0].get('file_id')
            logger.info(f"Using RAG file_id for document: {doc_id}")
        elif source_uri and source_uri.startswith("gs://"):
            resolved_doc_id = resolve_rag_file_id(
                filename=file.filename,
                source_uri=source_uri,
                db_created_at=datetime.utcnow(),
            )
            if resolved_doc_id:
                doc_id = resolved_doc_id
                logger.info(f"Resolved RAG file_id from corpus metadata: {doc_id}")
            else:
                doc_id = hashlib.md5(source_uri.encode()).hexdigest()[:16]
                logger.info(f"Using source_uri-based fallback ID for document: {doc_id} (from {source_uri})")
        else:
            resolved_doc_id = resolve_rag_file_id(
                filename=file.filename,
                source_uri=source_uri,
                db_created_at=datetime.utcnow(),
            )
            if resolved_doc_id:
                doc_id = resolved_doc_id
                logger.info(f"Resolved RAG file_id from corpus metadata: {doc_id}")
            else:
                doc_id = hashlib.md5(f"{file.filename}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
                logger.info(f"Using fallback ID for document: {doc_id}")
        

        
        # Record in database
        try:
            db_doc = KnowledgeBaseDocument(
                doc_id=doc_id,
                filename=file.filename,
                file_extension=os.path.splitext(file.filename)[1],
                file_size_bytes=file_size,
                corpus_id="agent-lock",
                source_uri=source_uri,
                status="active",
                embedded_at=datetime.utcnow(),
                uploaded_by=admin_user.id,
            )

            db.add(db_doc)
            db.commit()
            db.refresh(db_doc)
        except Exception as e:
            logger.exception("Failed to record document in DB: %s", e)
            # No local temp files to clean up when uploading from memory
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save document record: {str(e)}"
            )
        
        # Clear corpus info cache
        cache = get_cache()
        cache.delete(CacheKey.corpus_info("agent-lock"))
        
        logger.info(f"Document {doc_id} recorded in database")
        
        return DocumentResponse.from_orm(db_doc)

    except Exception as e:
        logger.exception("Unhandled error in upload_document_handler: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading document: {str(e)}"
        )

    # Note: no local temp file created when using in-memory upload


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    status_filter: Optional[str] = None,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """
    List knowledge base documents.
    
    Args:
        status_filter: Filter by status (active, archived, deleted)
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        List of documents
    """
    query = db.query(KnowledgeBaseDocument).filter(
        KnowledgeBaseDocument.corpus_id == "agent-lock"
    )
    
    if status_filter:
        query = query.filter(KnowledgeBaseDocument.status == status_filter)
    
    documents = query.order_by(KnowledgeBaseDocument.created_at.desc()).all()
    
    return DocumentListResponse(
        total=len(documents),
        documents=[DocumentResponse.from_orm(doc) for doc in documents]
    )


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """
    Get document details.
    
    Args:
        doc_id: Document ID
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Document details
    """
    document = db.query(KnowledgeBaseDocument).filter(
        KnowledgeBaseDocument.doc_id == doc_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return DocumentResponse.from_orm(document)


@router.delete("/documents/{identifier}", response_model=dict)
async def delete_document_handler(
    identifier: str,
    delete_request: DocumentDeleteRequest,
    db: SQLSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
) -> dict:
    """
    Delete a document from the knowledge base.
    
    Args:
        doc_id: Document ID to delete
        delete_request: Deletion confirmation
        db: Database connection
        admin_user: Authenticated admin user (admin only)
    
    Returns:
        Deletion confirmation
    """
    # Find document
    # Attempt to locate document by db primary id or by stored doc_id (RAG file id)
    document = None
    try:
        # If identifier looks like an integer primary id, try that first
        possible_int = int(identifier)
        document = db.query(KnowledgeBaseDocument).filter(KnowledgeBaseDocument.id == possible_int).first()
    except Exception:
        document = None

    if not document:
        document = db.query(KnowledgeBaseDocument).filter(
            KnowledgeBaseDocument.doc_id == identifier
        ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Require confirmation
    if not delete_request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion requires confirmation (set confirm=true)"
        )
    
    # Delete from RAG corpus using the real corpus file_id.
    request_doc_id = delete_request.doc_id or document.doc_id
    request_filename = delete_request.filename or document.filename

    resolved_candidates = resolve_rag_file_candidates(
        filename=request_filename,
        source_uri=document.source_uri,
        expected_doc_id=request_doc_id,
        db_created_at=document.created_at,
    )

    delete_candidates: List[str] = []
    for candidate in resolved_candidates:
        if candidate not in delete_candidates:
            delete_candidates.append(candidate)
    if request_doc_id and request_doc_id not in delete_candidates:
        delete_candidates.append(request_doc_id)
    if document.doc_id and document.doc_id not in delete_candidates:
        delete_candidates.append(document.doc_id)
    if identifier and identifier not in delete_candidates:
        delete_candidates.append(identifier)

    rag_delete_result = None
    rag_doc_id = None
    delete_errors: List[str] = []

    for candidate_id in delete_candidates:
        rag_doc_id = candidate_id
        rag_delete_result = rag_delete_document(
            corpus_name="agent-lock",
            document_id=candidate_id,
            confirm=True,
            tool_context=None
        )
        if rag_delete_result.get("status") == "success":
            break
        delete_errors.append(rag_delete_result.get("message", "Unknown deletion error"))

    if not rag_delete_result or rag_delete_result.get("status") == "error":
        logger.warning("Failed to delete from RAG corpus after trying ids %s: %s", delete_candidates, delete_errors)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to delete document from corpus. "
                f"Tried IDs: {delete_candidates}. Errors: {delete_errors}"
            )
        )

    # Keep db doc_id in sync with the actual corpus file_id used for deletion.
    if rag_doc_id and document.doc_id != rag_doc_id:
        document.doc_id = rag_doc_id
    
    # Keep record for auditability; mark as deleted after corpus delete succeeds.
    deleted_filename = document.filename
    document.status = "deleted"
    document.updated_at = datetime.utcnow()
    db.commit()
    
    # Clear cache
    cache = get_cache()
    cache.delete(CacheKey.corpus_info("agent-lock"))
    cache.delete(CacheKey.document_metadata(rag_doc_id))
    
    logger.info(f"Document {rag_doc_id} ({deleted_filename}) deleted by user {admin_user.id}")
    
    return {
        "message": "Document deleted successfully",
        "doc_id": rag_doc_id,
        "filename": deleted_filename
    }


@router.get("/stats", response_model=dict)
async def get_knowledge_base_stats(
    db: SQLSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get knowledge base statistics.
    
    Args:
        db: Database connection
        current_user: Authenticated user
    
    Returns:
        Knowledge base statistics
    """
    total_docs = db.query(KnowledgeBaseDocument).filter(
        KnowledgeBaseDocument.corpus_id == "agent-lock"
    ).count()
    
    active_docs = db.query(KnowledgeBaseDocument).filter(
        KnowledgeBaseDocument.corpus_id == "agent-lock",
        KnowledgeBaseDocument.status == "active"
    ).count()
    
    total_size = db.query(KnowledgeBaseDocument).filter(
        KnowledgeBaseDocument.corpus_id == "agent-lock"
    ).with_entities(
        db.func.sum(KnowledgeBaseDocument.file_size_bytes)
    ).scalar() or 0
    
    return {
        "corpus_name": "agent-lock",
        "total_documents": total_docs,
        "active_documents": active_docs,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2)
    }


@router.post("/sync", response_model=dict)
async def sync_documents_from_corpus(
    db: SQLSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
) -> dict:
    """
    Sync documents from the RAG corpus to the database.
    
    This endpoint fetches all documents from the agent-lock RAG corpus
    and ensures they are recorded in the database. New documents are added,
    document IDs are corrected if needed, and deleted documents are marked as deleted.
    
    Args:
        db: Database connection
        admin_user: Authenticated admin user (admin only)
    
    Returns:
        Sync result with counts of synced documents
    """
    try:
        logger.info("Starting document sync from corpus")
        # Get corpus information including all files
        corpus_info = get_corpus_info(corpus_name="agent-lock", tool_context=None)
        logger.info(f"Corpus info retrieved: status={corpus_info.get('status')}, files={len(corpus_info.get('files', []))}")
        
        if corpus_info.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch corpus information: {corpus_info.get('message')}"
            )
        
        # Get list of files from RAG corpus
        rag_files = corpus_info.get("files", [])
        logger.info(f"Found {len(rag_files)} files in RAG corpus")
        rag_file_ids = set()
        
        # Track documents that were synced
        synced_count = 0
        activated_count = 0
        fixed_count = 0
        deleted_count = 0
        
        # Log all files found
        for rag_file in rag_files:
            logger.info(f"RAG file: id={rag_file.get('file_id')}, name={rag_file.get('display_name')}, source_uri={rag_file.get('source_uri')}")
        
        # Process each file in the RAG corpus
        for rag_file in rag_files:
            file_id = rag_file.get("file_id")
            filename = rag_file.get("display_name", f"Unknown_{file_id}")
            source_uri = rag_file.get("source_uri", "")
            
            logger.info(f"Processing RAG file: id={file_id}, filename={filename}, source_uri={source_uri}")
            
            if not file_id:
                logger.warning(f"Skipping file with no ID: {filename}")
                continue
            
            rag_file_ids.add(file_id)
            
            # First, try to find by actual file_id
            existing_doc = db.query(KnowledgeBaseDocument).filter(
                KnowledgeBaseDocument.doc_id == file_id
            ).first()
            
            # If not found by file_id, try by source_uri
            if not existing_doc and source_uri:
                existing_doc = db.query(KnowledgeBaseDocument).filter(
                    KnowledgeBaseDocument.source_uri == source_uri
                ).first()
                if existing_doc:
                    logger.info(f"Found existing document by source_uri, updating doc_id from {existing_doc.doc_id} to {file_id}")
                    # Update the doc_id to match the actual corpus file_id
                    existing_doc.doc_id = file_id
                    fixed_count += 1
            
            if existing_doc:
                logger.info(f"Document {file_id} already exists in database (status: {existing_doc.status})")
                # If document was previously deleted, reactivate it
                if existing_doc.status == "deleted":
                    existing_doc.status = "active"
                    existing_doc.updated_at = datetime.utcnow()
                    activated_count += 1
                    logger.info(f"Reactivated document {file_id}")
            else:
                # Create new document entry in database
                new_doc = KnowledgeBaseDocument(
                    doc_id=file_id,
                    filename=filename,
                    file_extension=os.path.splitext(filename)[1].lower() if filename else "",
                    file_size_bytes=0,  # Size not available from RAG corpus API
                    corpus_id="agent-lock",
                    source_uri=source_uri,
                    status="active",
                    embedded_at=datetime.utcnow(),
                    uploaded_by=admin_user.id if admin_user else None,
                )
                db.add(new_doc)
                synced_count += 1
                logger.info(f"Created new document entry for {file_id}")
        
        # Commit changes
        # Mark documents missing from corpus as deleted so the admin view
        # reflects the corpus as the source of truth.
        active_docs = db.query(KnowledgeBaseDocument).filter(
            KnowledgeBaseDocument.corpus_id == "agent-lock",
            KnowledgeBaseDocument.status == "active"
        ).all()

        for db_doc in active_docs:
            if db_doc.doc_id not in rag_file_ids:
                db_doc.status = "deleted"
                db_doc.updated_at = datetime.utcnow()
                deleted_count += 1
                logger.info(f"Marked missing corpus document as deleted: {db_doc.doc_id}")

        # Commit changes
        db.commit()
        
        # Clear cache
        cache = get_cache()
        cache.delete(CacheKey.corpus_info("agent-lock"))
        
        logger.info(
            f"Sync complete: {synced_count} new documents, {activated_count} reactivated, "
            f"{fixed_count} fixed doc_ids, {deleted_count} marked deleted, {len(rag_files)} total in corpus"
        )
        
        return {
            "status": "success",
            "message": "Documents synced successfully from RAG corpus",
            "synced_count": synced_count,
            "activated_count": activated_count,
            "fixed_count": fixed_count,
            "deleted_count": deleted_count,
            "total_files_in_corpus": len(rag_files)
        }
    
    except Exception as e:
        logger.exception(f"Error syncing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing documents: {str(e)}"
        )
