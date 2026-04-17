"""
Tool for creating a new Vertex AI RAG corpus.
"""

import re

from google.adk.tools.tool_context import ToolContext
from vertexai import rag

from ..config import (
    AGENT_LOCK_CORPUS,
    DEFAULT_EMBEDDING_MODEL,
)
from .utils import check_corpus_exists


def create_corpus(
    corpus_name: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """
    Create the agent-lock Vertex AI RAG corpus.
    
    Note: This system enforces a single corpus. Only the agent-lock corpus
    can be created. The corpus_name parameter is ignored if provided.

    Args:
        corpus_name (str): Ignored. The agent-lock corpus is always created.
        tool_context (ToolContext): The tool context for state management

    Returns:
        dict: Status information about the operation
    """
    # Enforce single corpus - always use AGENT_LOCK_CORPUS
    corpus_name = AGENT_LOCK_CORPUS
    # Check if corpus already exists
    if check_corpus_exists(corpus_name, tool_context):
        return {
            "status": "info",
            "message": f"Corpus '{corpus_name}' already exists",
            "corpus_name": corpus_name,
            "corpus_created": False,
        }

    try:
        # Clean corpus name for use as display name
        display_name = re.sub(r"[^a-zA-Z0-9_-]", "_", corpus_name)

        # Configure embedding model
        embedding_model_config = rag.RagEmbeddingModelConfig(
            vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                publisher_model=DEFAULT_EMBEDDING_MODEL
            )
        )

        # Create the corpus
        rag_corpus = rag.create_corpus(
            display_name=display_name,
            backend_config=rag.RagVectorDbConfig(
                rag_embedding_model_config=embedding_model_config
            ),
        )

        # Update state to track corpus existence
        if tool_context:
            tool_context.state[f"corpus_exists_{corpus_name}"] = True
            # Set this as the current corpus
            tool_context.state["current_corpus"] = corpus_name

        return {
            "status": "success",
            "message": f"Successfully created corpus '{corpus_name}'",
            "corpus_name": rag_corpus.name,
            "display_name": rag_corpus.display_name,
            "corpus_created": True,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error creating corpus: {str(e)}",
            "corpus_name": corpus_name,
            "corpus_created": False,
        }
