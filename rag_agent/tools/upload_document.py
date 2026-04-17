"""
Tool for uploading local files to the agent-lock RAG corpus.
"""

import os
import tempfile
from typing import Optional, TYPE_CHECKING

import logging

# Avoid importing runtime-only dependencies at module import time so the
# package can be imported in environments that don't have the VertexAI
# SDK installed. Use TYPE_CHECKING to keep static type checkers happy.
if TYPE_CHECKING:
    from google.adk.tools.tool_context import ToolContext

from ..config import (
    AGENT_LOCK_CORPUS,
)
from .utils import check_corpus_exists, get_corpus_resource_name

logger = logging.getLogger(__name__)


def upload_document(
    file_path: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    source_uri: Optional[str] = None,
    tool_context: Optional["ToolContext"] = None,
) -> dict:
    """
    Upload a file to the agent-lock RAG corpus from a local file path.

    This function accepts either a local `file_path` or raw `file_bytes`
    with an accompanying `filename`. For byte uploads, a temporary local
    file is created and passed to Vertex AI's `rag.upload_file` API.

    Args:
        file_path (str, optional): Local file path to upload.
        file_bytes (bytes, optional): Raw file bytes to upload (preferred).
        filename (str, optional): Filename to use when `file_bytes` is provided.
        source_uri (str, optional): Optional source path/URI metadata for the uploaded file
        tool_context (ToolContext, optional): The tool context

    Returns:
        dict: Information about the uploaded file and status
    """
    corpus_name = AGENT_LOCK_CORPUS

    # Supported file extensions
    supported_extensions = {
        '.pdf', '.docx', '.txt', '.doc', '.pptx', '.xlsx', '.csv', '.html', '.json', '.md'
    }

    temp_file_path = None

    # Validate input presence
    if file_bytes is None and not file_path:
        return {
            "status": "error",
            "message": "No file provided. Supply either file_path or file_bytes/filename.",
            "corpus_name": corpus_name,
            "file_path": file_path,
        }

    # Determine filename and extension
    if file_bytes is not None:
        file_size = len(file_bytes)
        file_name = filename or "uploaded_file"
        file_extension = os.path.splitext(file_name)[1].lower()
        file_path_for_return = source_uri
    else:
        # Local file path flow
        if not os.path.exists(file_path):
            logger.info("Upload aborted: file does not exist: %s", file_path)
            return {
                "status": "error",
                "message": f"File not found: {file_path}",
                "corpus_name": corpus_name,
                "file_path": file_path,
            }
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_name)[1].lower()
        file_path_for_return = file_path

    if file_extension not in supported_extensions:
        logger.info("Upload aborted: unsupported extension %s for file %s", file_extension, file_name)
        return {
            "status": "error",
            "message": (
                f"Unsupported file type: {file_extension}. "
                f"Supported types: {', '.join(sorted(supported_extensions))}"
            ),
            "corpus_name": corpus_name,
            "file_path": file_path_for_return,
        }
    
    # Check if the corpus exists, create if it doesn't
    if not check_corpus_exists(corpus_name, tool_context):
        from .create_corpus import create_corpus
        create_result = create_corpus(corpus_name, tool_context)
        if create_result.get("status") == "error":
            return {
                "status": "error",
                "message": f"Could not create corpus '{corpus_name}'. {create_result.get('message', '')}",
                "corpus_name": corpus_name,
                "file_path": file_path_for_return,
            }
    
    try:
        logger.info("Starting upload for file: %s", file_name)

        # Get the corpus resource name
        corpus_resource_name = get_corpus_resource_name(corpus_name)
        logger.info("Corpus resource resolved: %s", corpus_resource_name)
        # Import Vertex AI RAG SDK at runtime so module import doesn't fail
        # in environments where the SDK isn't installed.
        try:
            from vertexai import rag
        except Exception as import_err:
            logger.exception("VertexAI SDK import failed: %s", import_err)
            return {
                "status": "error",
                "message": (
                    "Vertex AI SDK not available: cannot import files to RAG corpus. "
                    "Install the required 'vertexai' package or configure the environment."
                ),
                "corpus_name": corpus_name,
                "file_path": file_path_for_return if 'file_path_for_return' in locals() else None,
            }

        # For in-memory uploads, persist to a temporary local file so we can
        # always use rag.upload_file(path=...).
        upload_path = file_path
        if file_bytes is not None:
            temp_file = tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=file_extension,
                prefix="agent-lock-upload-",
                delete=False,
            )
            try:
                temp_file.write(file_bytes)
                temp_file.flush()
                upload_path = temp_file.name
                temp_file_path = temp_file.name
            finally:
                temp_file.close()

        description = (
            f"Uploaded from local path: {source_uri}" if source_uri else "Uploaded from local machine"
        )

        logger.info("Uploading local file to RAG corpus: %s", upload_path)
        uploaded_file = rag.upload_file(
            corpus_name=corpus_resource_name,
            path=upload_path,
            display_name=file_name,
            description=description,
        )

        file_resource_name = getattr(uploaded_file, "name", None) or getattr(uploaded_file, "resource", None)
        file_id = file_resource_name.split("/")[-1] if file_resource_name and "/" in file_resource_name else None
        uploaded_source_uri = getattr(uploaded_file, "source_uri", None)

        file_entries = [
            {
                "resource_name": file_resource_name,
                "file_id": file_id,
                "display_name": getattr(uploaded_file, "display_name", None) or file_name,
                "source_uri": uploaded_source_uri,
            }
        ]

        # Set this as the current corpus if not already set
        if tool_context:
            if not tool_context.state.get("current_corpus"):
                tool_context.state["current_corpus"] = corpus_name

        return {
            "status": "success",
            "message": f"Successfully uploaded '{file_name}' to corpus '{corpus_name}'",
            "corpus_name": corpus_name,
            "file_path": file_path_for_return if 'file_path_for_return' in locals() else None,
            "file_uri": uploaded_source_uri,
            "file_name": file_name,
            "file_size_bytes": file_size,
            "files_added": 1,
            "file_entries": file_entries,
        }
    except Exception as e:
        logger.exception("Unhandled error in upload_document: %s", e)
        return {
            "status": "error",
            "message": f"Error uploading document: {str(e)}",
            "corpus_name": corpus_name,
            "file_path": file_path_for_return if 'file_path_for_return' in locals() else None,
        }
    finally:
        # Best-effort cleanup for temporary files created from in-memory uploads.
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as cleanup_err:
                logger.warning("Failed to remove temp upload file %s: %s", temp_file_path, cleanup_err)
