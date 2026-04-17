"""
Tool for managing the agent-lock RAG corpus (preventing accidental deletion).
"""

from google.adk.tools.tool_context import ToolContext
from vertexai import rag

from ..config import AGENT_LOCK_CORPUS
from .utils import check_corpus_exists, get_corpus_resource_name


def delete_corpus(
    corpus_name: str = "",
    confirm: bool = False,
    tool_context: ToolContext = None,
) -> dict:
    """
    Prevent deletion of the agent-lock RAG corpus.
    
    The agent-lock corpus is critical to the system and cannot be deleted.
    This function is kept for API compatibility but will always refuse to delete.

    Args:
        corpus_name (str): Ignored. The agent-lock corpus cannot be deleted.
        confirm (bool): Ignored. The agent-lock corpus cannot be deleted.
        tool_context (ToolContext): The tool context

    Returns:
        dict: Status information indicating deletion is not allowed
    """
    corpus_name = AGENT_LOCK_CORPUS
    
    return {
        "status": "error",
        "message": f"The '{AGENT_LOCK_CORPUS}' corpus is critical to the system and cannot be deleted. Please contact administrator if you need to clear this corpus.",
        "corpus_name": corpus_name,
        "corpus_deleted": False,
    }
