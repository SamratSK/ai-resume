"""In-memory job status tracker for long operations (resume upload+extract,
shortlist scoring). Simplest acceptable approach: a background thread does
the work, the frontend polls GET /api/jobs/{id} for status/progress/result.
Threads (not asyncio tasks) because the Stage 1/2 pipelines are fully
synchronous/blocking (httpx sync client, docling sync calls).
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class Job:
    id: str
    status: str = "pending"  # pending | running | done | error
    progress: str = ""
    result: Any = None
    error: Optional[str] = None


class JobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, fn: Callable[[Job], Any]) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id)
        with self._lock:
            self._jobs[job_id] = job
        threading.Thread(target=self._run, args=(job, fn), daemon=True).start()
        return job_id

    def _run(self, job: Job, fn: Callable[[Job], Any]) -> None:
        job.status = "running"
        try:
            job.result = fn(job)
            job.status = "done"
        except Exception as exc:  # the job endpoint surfaces this; it never crashes the server
            job.status = "error"
            job.error = str(exc)

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)


job_manager = JobManager()
