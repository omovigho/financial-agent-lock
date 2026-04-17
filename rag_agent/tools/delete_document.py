"""
Tool for deleting a specific document from the agent-lock RAG corpus.
"""

from google.adk.tools.tool_context import ToolContext
from vertexai import rag

from ..config import AGENT_LOCK_CORPUS
from .utils import check_corpus_exists, get_corpus_resource_name


def delete_document(
    corpus_name: str = "",
    document_id: str = "",
    confirm: bool = False,
    tool_context: ToolContext = None,
) -> dict:
    """
    Delete a specific document from the agent-lock RAG corpus.
    
    Requires confirmation to prevent accidental deletion.

    Args:
        corpus_name (str): Ignored. Always deletes from the agent-lock corpus.
        document_id (str): The ID of the specific document/file to delete. 
                          Can be obtained from get_corpus_info results.
        confirm (bool): Must be set to True to confirm deletion
        tool_context (ToolContext): The tool context

    Returns:
        dict: Status information about the deletion operation
    """
    # Enforce single corpus
    corpus_name = AGENT_LOCK_CORPUS
    
    # Check if deletion is confirmed
    if not confirm:
        return {
            "status": "error",
            "message": "Deletion requires explicit confirmation. Set confirm=True to delete this document.",
            "corpus_name": corpus_name,
            "document_id": document_id,
        }
    
    # Check if corpus exists
    if not check_corpus_exists(corpus_name, tool_context):
        return {
            "status": "error",
            "message": f"Corpus '{corpus_name}' does not exist",
            "corpus_name": corpus_name,
            "document_id": document_id,
        }

    try:
        # Get the corpus resource name
        corpus_resource_name = get_corpus_resource_name(corpus_name)

        # Delete the document
        rag_file_path = f"{corpus_resource_name}/ragFiles/{document_id}"
        rag.delete_file(rag_file_path)

        return {
            "status": "success",
            "message": f"Successfully deleted document '{document_id}' from corpus '{corpus_name}'",
            "corpus_name": corpus_name,
            "document_id": document_id,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error deleting document: {str(e)}",
            "corpus_name": corpus_name,
            "document_id": document_id,
        }
