"""
Tool for listing the agent-lock Vertex AI RAG corpus.
"""

from typing import Dict, List, Union

from vertexai import rag

from ..config import AGENT_LOCK_CORPUS


def list_corpora(corpus_name: str = "") -> dict:
    """
    List the agent-lock Vertex AI RAG corpus.
    
    Note: This system enforces a single corpus for all operations.
    The corpus_name parameter is ignored; only the agent-lock corpus is available.

    Returns:
        dict: Information about the agent-lock corpus and status
    """
    try:
        # Get the list of corpora
        corpora = rag.list_corpora()

        # Filter for agent-lock corpus only
        corpus_info: List[Dict[str, Union[str, int]]] = []
        for corpus in corpora:
            # Check if this is our agent-lock corpus
            if hasattr(corpus, 'display_name') and corpus.display_name == AGENT_LOCK_CORPUS:
                corpus_data: Dict[str, Union[str, int]] = {
                    "resource_name": corpus.name,
                    "display_name": corpus.display_name,
                    "create_time": (
                        str(corpus.create_time) if hasattr(corpus, "create_time") else ""
                    ),
                    "update_time": (
                        str(corpus.update_time) if hasattr(corpus, "update_time") else ""
                    ),
                }
                corpus_info.append(corpus_data)

        # If no agent-lock corpus found, suggest creating it
        if not corpus_info:
            return {
                "status": "info",
                "message": f"The '{AGENT_LOCK_CORPUS}' corpus does not exist yet. It will be created automatically when needed.",
                "corpora": [],
                "corpus_name": AGENT_LOCK_CORPUS,
            }

        return {
            "status": "success",
            "message": f"Agent-Lock corpus is available",
            "corpora": corpus_info,
            "corpus_name": AGENT_LOCK_CORPUS,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error listing corpus: {str(e)}",
            "corpora": [],
            "corpus_name": AGENT_LOCK_CORPUS,
        }
