"""
Async Processing - Phase 2 Performance Optimization

Implements message queue-based async processing for:
- Async certification requests
- Background rotor computation
- Batch processing
- Worker pool management

Expected improvements:
- 2x API response time reduction
- Non-blocking certification
- Better resource utilization
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import uuid
import json

try:
    from celery import Celery, Task
    from celery.result import AsyncResult
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


class TaskStatus(str, Enum):
    """Async task status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class AsyncRequest:
    """Async certification request."""
    request_id: str
    prompt: str
    model: Optional[str] = None
    domain: str = "research"
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


@dataclass
class AsyncResult:
    """Async certification result."""
    request_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class AsyncCertificationClient:
    """
    Client for async certification requests.

    Uses Celery + RabbitMQ for message queue processing.

    Architecture:
        Client → API → Queue (RabbitMQ) → Worker → Result Store (Redis) → Client

    Usage:
        client = AsyncCertificationClient(broker="pyamqp://localhost")

        # Submit async request
        request_id = client.submit("Your prompt here")

        # Check status
        status = client.get_status(request_id)

        # Get result (blocking)
        result = client.get_result(request_id, timeout=30)
    """

    def __init__(
        self,
        broker: str = "pyamqp://guest@localhost//",
        backend: str = "redis://localhost:6379/0",
        task_timeout: int = 300,  # 5 minutes
        result_expires: int = 3600,  # 1 hour
    ):
        """
        Initialize async certification client.

        Args:
            broker: Message broker URL (RabbitMQ)
            backend: Result backend URL (Redis)
            task_timeout: Task timeout in seconds
            result_expires: Result expiration in seconds
        """
        if not CELERY_AVAILABLE:
            raise ImportError("Celery not installed. Install with: pip install celery")

        self.broker = broker
        self.backend = backend
        self.task_timeout = task_timeout
        self.result_expires = result_expires

        # Initialize Celery app
        self.app = Celery(
            'swarm_it_async',
            broker=broker,
            backend=backend
        )

        # Configure
        self.app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_time_limit=task_timeout,
            result_expires=result_expires,
        )

        # Register tasks
        self._register_tasks()

    def _register_tasks(self):
        """Register Celery tasks."""

        @self.app.task(bind=True, name='certify_async')
        def certify_async_task(self, request_data: Dict[str, Any]):
            """
            Async certification task.

            This runs in worker process.
            """
            try:
                # Import here to avoid circular dependencies
                from swarm_it_adk import RSCTCertifier

                request = AsyncRequest(**request_data)

                # Update status to processing
                self.update_state(
                    state='PROCESSING',
                    meta={'request_id': request.request_id, 'status': 'processing'}
                )

                # Run certification
                certifier = RSCTCertifier()
                result = certifier.certify(request.prompt)

                # Return result
                return {
                    'request_id': request.request_id,
                    'status': 'completed',
                    'result': asdict(result),
                    'completed_at': datetime.utcnow().isoformat()
                }

            except Exception as e:
                # Task failed
                return {
                    'request_id': request.request_id,
                    'status': 'failed',
                    'error': str(e),
                    'completed_at': datetime.utcnow().isoformat()
                }

        self.certify_task = certify_async_task

    def submit(
        self,
        prompt: str,
        model: Optional[str] = None,
        domain: str = "research",
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> str:
        """
        Submit async certification request.

        Args:
            prompt: Text to certify
            model: Model name (optional)
            domain: Certification domain
            user_id: User ID for audit
            org_id: Organization ID for audit

        Returns:
            Request ID for tracking
        """
        request_id = str(uuid.uuid4())

        request = AsyncRequest(
            request_id=request_id,
            prompt=prompt,
            model=model,
            domain=domain,
            user_id=user_id,
            org_id=org_id
        )

        # Submit to queue
        self.certify_task.apply_async(
            args=[asdict(request)],
            task_id=request_id
        )

        return request_id

    def get_status(self, request_id: str) -> TaskStatus:
        """
        Get task status.

        Args:
            request_id: Request ID

        Returns:
            Current task status
        """
        task_result = AsyncResult(request_id, app=self.app)

        if task_result.ready():
            if task_result.successful():
                return TaskStatus.COMPLETED
            else:
                return TaskStatus.FAILED
        elif task_result.state == 'PROCESSING':
            return TaskStatus.PROCESSING
        else:
            return TaskStatus.PENDING

    def get_result(self, request_id: str, timeout: Optional[float] = None) -> AsyncResult:
        """
        Get task result (blocking).

        Args:
            request_id: Request ID
            timeout: Timeout in seconds (None = wait forever)

        Returns:
            AsyncResult with certification result or error

        Raises:
            TimeoutError: If timeout exceeded
        """
        task_result = AsyncResult(request_id, app=self.app)

        try:
            # Wait for result
            result_data = task_result.get(timeout=timeout)

            return AsyncResult(
                request_id=result_data['request_id'],
                status=TaskStatus(result_data['status']),
                result=result_data.get('result'),
                error=result_data.get('error'),
                completed_at=result_data.get('completed_at')
            )

        except Exception as e:
            return AsyncResult(
                request_id=request_id,
                status=TaskStatus.FAILED,
                error=str(e),
                completed_at=datetime.utcnow().isoformat()
            )

    def cancel(self, request_id: str) -> bool:
        """
        Cancel pending/processing task.

        Args:
            request_id: Request ID

        Returns:
            True if cancelled successfully
        """
        task_result = AsyncResult(request_id, app=self.app)
        task_result.revoke(terminate=True)
        return True


class BatchProcessor:
    """
    Batch processing for multiple certifications.

    Processes multiple requests in parallel using worker pool.

    Usage:
        processor = BatchProcessor(client=async_client)

        # Submit batch
        request_ids = processor.submit_batch(prompts)

        # Wait for all results
        results = processor.get_batch_results(request_ids, timeout=60)
    """

    def __init__(self, client: AsyncCertificationClient):
        """
        Initialize batch processor.

        Args:
            client: Async certification client
        """
        self.client = client

    def submit_batch(
        self,
        prompts: List[str],
        model: Optional[str] = None,
        domain: str = "research",
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[str]:
        """
        Submit batch of certification requests.

        Args:
            prompts: List of prompts to certify
            model: Model name (optional)
            domain: Certification domain
            user_id: User ID for audit
            org_id: Organization ID for audit

        Returns:
            List of request IDs
        """
        request_ids = []

        for prompt in prompts:
            request_id = self.client.submit(
                prompt=prompt,
                model=model,
                domain=domain,
                user_id=user_id,
                org_id=org_id
            )
            request_ids.append(request_id)

        return request_ids

    def get_batch_results(
        self,
        request_ids: List[str],
        timeout: Optional[float] = None
    ) -> List[AsyncResult]:
        """
        Get results for batch of requests.

        Args:
            request_ids: List of request IDs
            timeout: Timeout per request in seconds

        Returns:
            List of AsyncResults
        """
        results = []

        for request_id in request_ids:
            result = self.client.get_result(request_id, timeout=timeout)
            results.append(result)

        return results

    def get_batch_status(self, request_ids: List[str]) -> Dict[str, int]:
        """
        Get status summary for batch.

        Args:
            request_ids: List of request IDs

        Returns:
            Status counts {pending: X, processing: Y, completed: Z, failed: W}
        """
        status_counts = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0
        }

        for request_id in request_ids:
            status = self.client.get_status(request_id)
            status_counts[status.value] += 1

        return status_counts


# Worker configuration (for running Celery workers)

def create_worker_app(
    broker: str = "pyamqp://guest@localhost//",
    backend: str = "redis://localhost:6379/0",
    concurrency: int = 4,
) -> Celery:
    """
    Create Celery worker app.

    Run workers with:
        celery -A swarm_it.async_processing worker --loglevel=info --concurrency=4

    Args:
        broker: Message broker URL
        backend: Result backend URL
        concurrency: Number of worker processes

    Returns:
        Configured Celery app
    """
    app = Celery(
        'swarm_it_worker',
        broker=broker,
        backend=backend
    )

    app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        worker_prefetch_multiplier=1,
        worker_concurrency=concurrency,
    )

    return app


# Convenience functions

def submit_async_certification(
    prompt: str,
    broker: str = "pyamqp://guest@localhost//",
    backend: str = "redis://localhost:6379/0",
    **kwargs
) -> str:
    """
    Convenience function to submit async certification.

    Args:
        prompt: Text to certify
        broker: Message broker URL
        backend: Result backend URL
        **kwargs: Additional request parameters

    Returns:
        Request ID
    """
    client = AsyncCertificationClient(broker=broker, backend=backend)
    return client.submit(prompt, **kwargs)


def get_async_result(
    request_id: str,
    broker: str = "pyamqp://guest@localhost//",
    backend: str = "redis://localhost:6379/0",
    timeout: Optional[float] = None
) -> AsyncResult:
    """
    Convenience function to get async result.

    Args:
        request_id: Request ID
        broker: Message broker URL
        backend: Result backend URL
        timeout: Timeout in seconds

    Returns:
        AsyncResult
    """
    client = AsyncCertificationClient(broker=broker, backend=backend)
    return client.get_result(request_id, timeout=timeout)
