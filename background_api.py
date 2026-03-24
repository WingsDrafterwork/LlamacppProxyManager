"""
FastAPI wrapper endpoints for background job queue.
Provides /v1/background/chat/completions endpoints that mimic OpenAI's async pattern.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from background_queue import BackgroundQueue, JobStatus

logger = logging.getLogger(__name__)


class ChatCompletionRequest(BaseModel):
    """Chat completion request model"""
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


class BackgroundJobResponse(BaseModel):
    """Response for background job submission"""
    id: str
    status: str
    created_at: str


class JobStatusResponse(BaseModel):
    """Response for job status poll"""
    id: str
    status: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def create_background_api(app: FastAPI, queue: BackgroundQueue):
    """
    Register background queue endpoints on a FastAPI app.
    
    Args:
        app: FastAPI application instance
        queue: BackgroundQueue instance
    """
    
    @app.post("/v1/background/chat/completions", response_model=BackgroundJobResponse)
    async def submit_chat_completion(request: ChatCompletionRequest):
        """
        Submit a chat completion request to the background queue.
        
        Returns immediately with a job ID for polling.
        This mimics OpenAI's background: true pattern.
        
        Example:
            POST /v1/background/chat/completions
            {
                "model": "llama2",
                "messages": [{"role": "user", "content": "Hello!"}]
            }
            
            Returns:
            {
                "id": "job_abc123...",
                "status": "queued",
                "created_at": "2026-03-24T12:00:00"
            }
        """
        payload = request.model_dump(exclude_none=True)
        result = await queue.submit(payload)
        return result
    
    @app.get("/v1/background/chat/completions/{job_id}", response_model=JobStatusResponse)
    async def poll_chat_completion(job_id: str):
        """
        Poll the status of a background chat completion job.
        
        Args:
            job_id: Job ID returned from submit endpoint
            
        Returns:
            Job status, and result if completed
            
        Example:
            GET /v1/background/chat/completions/job_abc123...
            
            Queued response:
            {
                "id": "job_abc123...",
                "status": "queued",
                "created_at": "2026-03-24T12:00:00"
            }
            
            Completed response:
            {
                "id": "job_abc123...",
                "status": "completed",
                "result": {
                    "choices": [{"message": {"content": "Hello!"}}],
                    ...
                }
            }
        """
        job = await queue.poll(job_id)
        
        if job.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return job
    
    @app.get("/v1/background/jobs")
    async def list_jobs(
        status: Optional[str] = Query(None, description="Filter by job status"),
        limit: int = Query(100, ge=1, le=1000, description="Max jobs to return")
    ):
        """
        List all background jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter (queued, in_progress, completed, failed, cancelled)
            limit: Maximum number of jobs to return (default 100, max 1000)
            
        Returns:
            List of job objects
            
        Example:
            GET /v1/background/jobs?status=completed&limit=50
        """
        jobs = await queue.list_jobs(status=status, limit=limit)
        return {"jobs": jobs, "count": len(jobs)}
    
    @app.post("/v1/background/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        """
        Cancel a queued job (only works if not yet in_progress).
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            Updated job status
            
        Example:
            POST /v1/background/jobs/job_abc123.../cancel
        """
        result = await queue.cancel(job_id)
        
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    
    @app.post("/v1/background/cleanup")
    async def cleanup_jobs(max_age_hours: int = Query(24, ge=1, description="Max age in hours")):
        """
        Clean up old completed/failed jobs.
        
        Args:
            max_age_hours: Remove jobs older than this many hours
            
        Returns:
            Number of jobs removed
            
        Example:
            POST /v1/background/cleanup?max_age_hours=48
        """
        removed = await queue.cleanup(max_age_hours=max_age_hours)
        return {"removed": removed, "message": f"Cleaned up {removed} old jobs"}
    
    logger.info("Background queue API endpoints registered")
