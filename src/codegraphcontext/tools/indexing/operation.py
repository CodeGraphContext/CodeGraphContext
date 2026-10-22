"""Cooperative cancellation and ownership of one full indexing operation."""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Awaitable, Callable, Optional

from ...core.jobs import JobManager, JobStatus


class IndexingOperation:
    """Keep the caller alive until its actual workers have released resources.

    Cancelling an asyncio.to_thread await does not stop its thread. Shield the
    entire pipeline instead: cancellation requests stop later phases, while the
    current native/subprocess call and admitted parse workers are allowed to
    finish. The returned task therefore remains a useful shutdown drain handle.
    """

    def __init__(self, job_manager: JobManager, job_id: Optional[str]):
        self.job_manager = job_manager
        self.job_id = job_id
        self._stopped = threading.Event()
        self._cancelled = threading.Event()

    def request_cancel(self) -> None:
        self._cancelled.set()
        self._stopped.set()
        if self.job_id:
            self.job_manager.cancel_job(self.job_id)

    def is_cancel_requested(self) -> bool:
        return self._cancelled.is_set() or (
            self.job_id is not None and self.job_manager.is_cancel_requested(self.job_id)
        )

    def check_cancelled(self, error: Optional[Exception] = None) -> None:
        """Check before admitting a phase, including from a blocking worker."""
        cancelled = self.is_cancel_requested()
        if self._stopped.is_set() or cancelled:
            if error is not None and cancelled and self.job_id:
                self.job_manager.fail_job(self.job_id, error)
            raise asyncio.CancelledError from error

    async def run_in_thread(self, function: Callable[..., Any], *args, **kwargs) -> Any:
        """Check both sides of a blocking phase, and again at executor admission."""
        self.check_cancelled()

        def call():
            self.check_cancelled()
            return function(*args, **kwargs)

        try:
            result = await asyncio.to_thread(call)
        except Exception as error:
            # A real failure racing cancellation is still useful evidence.
            self.check_cancelled(error)
            raise
        self.check_cancelled()
        return result

    async def drain(self, tasks: list[asyncio.Task]) -> None:
        """Stop queued parse admission, then wait for every admitted parse task."""
        if any(not task.done() for task in tasks):
            self._stopped.set()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run(self, work: Callable[[IndexingOperation], Awaitable[Any]]) -> Any:
        """Admit, supervise and finalize a pipeline without cancelling its worker."""
        if self.job_id and not self.job_manager.begin_job(self.job_id):
            if self.job_manager.is_cancel_requested(self.job_id):
                raise asyncio.CancelledError
            raise ValueError(f"Job {self.job_id} is not available for indexing")

        task = asyncio.create_task(work(self))
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                self.request_cancel()
                # Repeated cancellation requests must not interrupt draining.
            except Exception:
                break

        error = None
        result = None
        try:
            result = task.result()
        except asyncio.CancelledError:
            self.request_cancel()
        except Exception as caught:
            error = caught
            if self.job_id:
                self.job_manager.fail_job(self.job_id, caught)

        status = self.job_manager.finish_job(self.job_id) if self.job_id else None
        if self._cancelled.is_set() or status == JobStatus.CANCELLED:
            raise asyncio.CancelledError from error
        if error is not None:
            raise error
        return result
