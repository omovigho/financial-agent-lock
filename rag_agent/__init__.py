"""
Vertex AI RAG Agent

A package for interacting with Google Cloud Vertex AI RAG capabilities.
"""

import os
import logging

import vertexai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get Vertex AI configuration from environment
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION")

# Initialize Vertex AI at package load time
try:
    if PROJECT_ID and LOCATION:
        logger.info("Initializing Vertex AI with project=%s, location=%s", PROJECT_ID, LOCATION)
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        logger.info("Vertex AI initialization successful")
    else:
        logger.warning(
            "Missing Vertex AI configuration. PROJECT_ID=%s, LOCATION=%s. Tools requiring Vertex AI may not work properly.",
            PROJECT_ID,
            LOCATION,
        )
except Exception as e:
    logger.error("Failed to initialize Vertex AI: %s", str(e))
    logger.error("Please check your Google Cloud credentials and project settings.")

# Import agent after initialization is complete
from . import agent
