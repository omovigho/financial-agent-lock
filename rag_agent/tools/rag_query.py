"""
Tool for querying Vertex AI RAG corpora and retrieving relevant information.
"""

import logging

from google.adk.tools.tool_context import ToolContext
from vertexai import rag

from ..config import (
    AGENT_LOCK_CORPUS,
    DEFAULT_DISTANCE_THRESHOLD,
    DEFAULT_TOP_K,
)
from .utils import check_corpus_exists, get_corpus_resource_name


def rag_query(
    corpus_name: str = "",
    query: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """
    Query a Vertex AI RAG corpus with a user question and return relevant information.

    Args:
        corpus_name (str): The name of the corpus to query. Defaults to 'agent-lock'.
                          Must be the agent-lock corpus (enforced).
        query (str): The text query to search for in the corpus
        tool_context (ToolContext): The tool context

    Returns:
        dict: The query results and status
    """
    # Enforce single corpus
    if corpus_name and corpus_name != AGENT_LOCK_CORPUS:
        return {
            "status": "error",
            "message": f"Only the '{AGENT_LOCK_CORPUS}' corpus is allowed. Provided: '{corpus_name}'",
            "query": query,
            "corpus_name": AGENT_LOCK_CORPUS,
        }
    
    corpus_name = AGENT_LOCK_CORPUS
    
    try:
        logging.info("Starting RAG query for corpus '%s' with query: %s", corpus_name, query)
        # Check if the corpus exists, create if it doesn't
        if not check_corpus_exists(corpus_name, tool_context):
            from .create_corpus import create_corpus
            create_result = create_corpus(corpus_name, tool_context)
            if create_result.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"Corpus '{corpus_name}' does not exist and could not be created. {create_result.get('message', '')}",
                    "query": query,
                    "corpus_name": corpus_name,
                }

        # Get the corpus resource name
        corpus_resource_name = get_corpus_resource_name(corpus_name)

        # Configure retrieval parameters
        rag_retrieval_config = rag.RagRetrievalConfig(
            top_k=DEFAULT_TOP_K,
            filter=rag.Filter(vector_distance_threshold=DEFAULT_DISTANCE_THRESHOLD),
        )

        # Perform the query
        logging.info("Performing retrieval query with top_k=%s distance_threshold=%s", DEFAULT_TOP_K, DEFAULT_DISTANCE_THRESHOLD)
        try:
            response = rag.retrieval_query(
            rag_resources=[
                rag.RagResource(
                    rag_corpus=corpus_resource_name,
                )
            ],
            text=query,
            rag_retrieval_config=rag_retrieval_config,
            )
        except Exception as e:
            # Log and return the error so callers can inspect
            logging.exception("Error during rag.retrieval_query: %s", e)
            # Attempt to list files for debugging
            try:
                files = rag.list_files(corpus_resource_name)
                file_list = [getattr(f, 'display_name', None) or getattr(f, 'source_uri', None) or getattr(f, 'name', None) for f in files]
            except Exception:
                file_list = None
            return {
                "status": "error",
                "message": f"Error during retrieval query: {str(e)}",
                "query": query,
                "corpus_name": corpus_name,
                "corpus_files": file_list,
            }

        # Log raw response for debugging
        try:
            logging.info("Retrieving RAG response...")
        except Exception:
            pass

        # Process the response into a more usable format
        results = []
        if hasattr(response, "contexts") and response.contexts:
            for ctx_group in response.contexts.contexts:
                result = {
                    "source_uri": (
                        ctx_group.source_uri if hasattr(ctx_group, "source_uri") else ""
                    ),
                    "source_name": (
                        ctx_group.source_display_name
                        if hasattr(ctx_group, "source_display_name")
                        else ""
                    ),
                    "text": ctx_group.text if hasattr(ctx_group, "text") else "",
                    "score": ctx_group.score if hasattr(ctx_group, "score") else 0.0,
                }
                logging.info("Found context source")
                results.append(result)

        # If we didn't find any results
        if not results:
            # Attempt to list corpus files for debug visibility
            try:
                files = rag.list_files(corpus_resource_name)
                file_list = [getattr(f, 'display_name', None) or getattr(f, 'source_uri', None) or getattr(f, 'name', None) for f in files]
            except Exception:
                file_list = None
            return {
                "status": "warning",
                "message": f"No results found in corpus '{corpus_name}' for query: '{query}'",
                "query": query,
                "corpus_name": corpus_name,
                "results": [],
                "results_count": 0,
                "corpus_files": file_list,
            }

        return {
            "status": "success",
            "message": f"Successfully queried corpus '{corpus_name}'",
            "query": query,
            "corpus_name": corpus_name,
            "results": results,
            "results_count": len(results),
        }

    except Exception as e:
        error_msg = f"Error querying corpus: {str(e)}"
        logging.error(error_msg)
        return {
            "status": "error",
            "message": error_msg,
            "query": query,
            "corpus_name": corpus_name,
        }
