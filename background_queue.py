"""
Background queue system for llama.cpp inference requests.
Implements async job queuing with polling support, compatible with OpenAI's background: true pattern.
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import logging

from openai import AsyncOpenAI
import httpx

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


dataclass
class Job:
    """Job data structure"""
    id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary, handling non-serializable types"""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data


class BackgroundQueue:
    """
    In-memory background job queue for llama.cpp inference.
    
    Mimics OpenAI's background: true + polling pattern.
    Suitable for single-process deployments. For production,
    upgrade to Redis Queue (RQ) or Celery + Redis/RabbitMQ.
    """

    def __init__(self, base_url: str = "http://localhost:8000/v1", api_key: str = "none"):
        """Initialize the background queue. """
        
        Args:
            base_url: Base URL for llama.cpp server
            api_key: API key (default "none" for local llama.cpp)
        """
        self.base_url = base_url
        self.api_key = api_key
        self.jobs: Dict[str, Job] = {}
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        
    async def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit an inference request to the background queue. """
        
        Args:
            payload: Chat completion request payload
            
        Returns:
            Response with job ID and status
        """
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            status=JobStatus.QUEUED,
            created_at=datetime.utcnow(),
            payload=payload
        )
        self.jobs[job_id] = job
        
        # Schedule the inference task
        asyncio.create_task(self._run_inference(job_id, payload))
        
        logger.info(f"Job {job_id} submitted to background queue")
        
        return {
            "id": job_id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat()
        }
    
    async def poll(self, job_id: str) -> Dict[str, Any]:
        """Poll the status of a background job. """
        
        Args:
            job_id: The job ID to poll
            
        Returns:
            Job status and result (if completed)
        """
        job = self.jobs.get(job_id)
        
        if job is None:
            return {
                "status": "not_found",
                "error": f"Job {job_id} not found"
            }
        
        return job.to_dict()
    
    async def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status. """
        
        Args:
            status: Filter by status (optional)
            limit: Maximum number of jobs to return
            
        Returns:
            List of job dictionaries
        """
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status.value == status]
        
        return [job.to_dict() for job in jobs[-limit:]]
    
    async def cancel(self, job_id: str) -> Dict[str, Any]:
        """Cancel a queued job (only works if not yet in_progress). """
        
        Args:
            job_id: The job ID to cancel
            
        Returns:
            Updated job status
        """
        job = self.jobs.get(job_id)
        
        if job is None:
            return {
                "status": "not_found",
                "error": f"Job {job_id} not found"
            }
        
        if job.status == JobStatus.IN_PROGRESS:
            return {
                "status": "error",
                "error": "Cannot cancel job in progress"
            }
        
        job.status = JobStatus.CANCELLED
        logger.info(f"Job {job_id} cancelled")
        
        return job.to_dict()
    
    async def _run_inference(self, job_id: str, payload: Dict[str, Any]) -> None:
        """Internal method to run inference for a job. """ 
        
        Args:
            job_id: Job ID
            payload: Chat completion payload
        """ 
        job = self.jobs[job_id]
        
        try:
            job.status = JobStatus.IN_PROGRESS
            job.started_at = datetime.utcnow()
            
            logger.info(f"Job {job_id} starting inference")
            
            # Call llama.cpp via AsyncOpenAI
            response = await self.client.chat.completions.create(**payload)
            
            # Store result
            job.result = response.model_dump()
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            logger.error(f"Job {job_id} failed: {e}")
    
    async def cleanup(self, max_age_hours: int = 24) -> int:
        """Clean up old completed/failed jobs. """ 
        
        Args:
            max_age_hours: Jobs older than this are removed
            
        Returns:
            Number of jobs removed
        """ 
        now = datetime.utcnow()
        to_remove = []
        
        for job_id, job in self.jobs.items():
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                age = (now - job.completed_at).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(job_id)
        
        for job_id in to_remove:
            del self.jobs[job_id]
        
        logger.info(f"Cleaned up {len(to_remove)} old jobs")
        return len(to_remove)