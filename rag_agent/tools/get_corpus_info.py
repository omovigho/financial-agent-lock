"""
Tool for retrieving detailed information about the agent-lock RAG corpus.
"""

from google.adk.tools.tool_context import ToolContext
from vertexai import rag
import logging

from ..config import AGENT_LOCK_CORPUS
from .utils import check_corpus_exists, get_corpus_resource_name

logger = logging.getLogger(__name__)


def get_corpus_info(
    corpus_name: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """
    Get detailed information about the agent-lock RAG corpus, including its files.
    
    Note: This system enforces a single corpus. The corpus_name parameter is ignored.

    Args:
        corpus_name (str): Ignored. Always retrieves info for the agent-lock corpus.
        tool_context (ToolContext): The tool context

    Returns:
        dict: Information about the corpus and its files
    """
    # Enforce single corpus
    corpus_name = AGENT_LOCK_CORPUS
    try:
        # Check if corpus exists
        if not check_corpus_exists(corpus_name, tool_context):
            return {
                "status": "error",
                "message": f"Corpus '{corpus_name}' does not exist",
                "corpus_name": corpus_name,
            }

        # Get the corpus resource name
        corpus_resource_name = get_corpus_resource_name(corpus_name)
        logger.info(f"Getting corpus info for: {corpus_resource_name}")

        # Try to get corpus details first
        corpus_display_name = corpus_name  # Default if we can't get actual display name

        # Process file information
        file_details = []
        try:
            # Get the list of files
            files = rag.list_files(corpus_resource_name)
            logger.info(f"list_files returned: {type(files)}")
            
            file_count = 0
            for rag_file in files:
                file_count += 1
                logger.info(f"Processing file {file_count}: {rag_file}")
                logger.info(f"File attributes: {dir(rag_file)}")
                
                # Get document specific details
                try:
                    # Extract the file ID from the name
                    file_id = rag_file.name.split("/")[-1] if hasattr(rag_file, 'name') else None
                    display_name = rag_file.display_name if hasattr(rag_file, "display_name") else ""
                    source_uri = rag_file.source_uri if hasattr(rag_file, "source_uri") else ""
                    
                    logger.info(f"File details: id={file_id}, display_name={display_name}, source_uri={source_uri}")

                    file_info = {
                        "file_id": file_id,
                        "display_name": display_name,
                        "source_uri": source_uri,
                        "create_time": (
                            str(rag_file.create_time)
                            if hasattr(rag_file, "create_time")
                            else ""
                        ),
                        "update_time": (
                            str(rag_file.update_time)
                            if hasattr(rag_file, "update_time")
                            else ""
                        ),
                    }

                    file_details.append(file_info)
                except Exception as e:
                    logger.exception(f"Failed to parse file entry: {e}")
                    # Continue to the next file
                    continue
        except Exception as e:
            logger.exception(f"Failed to list files from corpus: {e}")
            # Continue without file details
            pass

        # Basic corpus info
        logger.info(f"Returning corpus info with {len(file_details)} files")
        return {
            "status": "success",
            "message": f"Successfully retrieved information for corpus '{corpus_display_name}'",
            "corpus_name": corpus_name,
            "corpus_display_name": corpus_display_name,
            "file_count": len(file_details),
            "files": file_details,
        }

    except Exception as e:
        logger.exception(f"Error in get_corpus_info: {e}")
        return {
            "status": "error",
            "message": f"Error getting corpus information: {str(e)}",
            "corpus_name": corpus_name,
        }
