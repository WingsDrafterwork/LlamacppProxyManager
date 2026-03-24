"""
Main application entry point for LlamacppProxyManager with background queue support.
Integrates the background job queue with FastAPI.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from background_queue import BackgroundQueue
from background_api import create_background_api

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
LLAMA_CPP_BASE_URL = os.getenv("LLAMA_CPP_BASE_URL", "http://localhost:8000/v1")
LLAMA_CPP_API_KEY = os.getenv("LLAMA_CPP_API_KEY", "none")
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "3600"))  # 1 hour
CLEANUP_MAX_AGE = int(os.getenv("CLEANUP_MAX_AGE_HOURS", "24"))  # 24 hours

# Global background queue instance
background_queue = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Handles startup and shutdown events.
    """
    global background_queue
    
    # Startup
    logger.info("Starting LlamacppProxyManager with background queue support")
    logger.info(f"Llama.cpp server: {LLAMA_CPP_BASE_URL}")
    
    background_queue = BackgroundQueue(
        base_url=LLAMA_CPP_BASE_URL,
        api_key=LLAMA_CPP_API_KEY
    )
    
    logger.info("Background queue initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down LlamacppProxyManager")
    # Optional: Perform final cleanup
    if background_queue:
        await background_queue.cleanup(max_age_hours=0)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="LlamacppProxyManager",
        description="OpenAI-compatible proxy for llama.cpp with background job queue support",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "service": "LlamacppProxyManager",
            "features": ["background_queue", "async_inference"]
        }
    
    # API info endpoint
    @app.get("/v1/models")
    async def list_models():
        """List available models (placeholder)"""
        return {
            "object": "list",
            "data": [
                {"id": "llama2", "object": "model", "owned_by": "llama.cpp"}
            ]
        }
    
    # Register background queue endpoints
    create_background_api(app, background_queue)
    
    logger.info("FastAPI application created and configured")
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )