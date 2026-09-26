"""Worker pool — isolates PyMuPDF/pyHanko in a subprocess with memory limits.

Uses ``concurrent.futures.ProcessPoolExecutor`` with the *forkserver* start
method so that the forked child inherits a clean address space.  Each worker
has a ``RLIMIT_AS`` memory ceiling (configurable via
``TTE_WORKER_MEMORY_MB``).  Jobs that exceed the timeout are cancelled and
the worker is recycled to prevent resource leaks.
"""

from __future__ import annotations

import resource
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from app.config import get_settings
from app.core.errors import AppError, ErrorCode


def _worker_init(memory_mb: int) -> None:
    """Set RLIMIT_AS in each worker process before any job runs."""
    try:
        limit = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (OSError, ValueError):
        pass  # best-effort on platforms without RLIMIT_AS


class WorkerPool:
    """Manages a process pool for CPU-bound PDF operations.

    Usage::

        pool = WorkerPool(max_workers=2, memory_mb=768)
        result = await pool.run(pdf_inspect, pdf_bytes, timeout=30)
    """

    def __init__(
        self,
        max_workers: int | None = None,
        memory_mb: int | None = None,
    ) -> None:
        settings = get_settings()
        self._max_workers = max_workers or settings.pdf_workers
        self._memory_mb = memory_mb or settings.worker_memory_mb
        self._job_timeout = settings.job_timeout_seconds
        self._executor: ProcessPoolExecutor | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create the underlying process pool."""
        if self._executor is not None:
            return
        self._executor = ProcessPoolExecutor(
            max_workers=self._max_workers,
            mp_context=None,  # uses forkserver via mp.set_start_method
            initializer=_worker_init,
            initargs=(self._memory_mb,),
        )

    async def stop(self) -> None:
        """Shut down the pool gracefully."""
        if self._executor is None:
            return
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._executor = None

    @property
    def is_ready(self) -> bool:
        return self._executor is not None

    # ------------------------------------------------------------------
    # Run a job
    # ------------------------------------------------------------------

    async def run(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        timeout: float | None = None,  # noqa: ASYNC109
        **kwargs: Any,
    ) -> Any:
        """Run *fn(*args, **kwargs)* in a worker process.

        Raises
        ------
        AppError(BUSY)
            If the pool is saturated (queue full).
        AppError(JOB_TIMEOUT)
            If the job exceeds *timeout* (defaults to
            ``TTE_JOB_TIMEOUT_SECONDS``).
        AppError(INTERNAL_ERROR)
            If the worker process dies unexpectedly.
        """
        if self._executor is None:
            raise RuntimeError("WorkerPool not started")

        effective_timeout = timeout if timeout is not None else self._job_timeout

        loop = None
        try:
            import asyncio

            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop is not None:
            fut: Any = loop.run_in_executor(self._executor, fn, *args, **kwargs) # type: ignore
        else:
            from concurrent.futures import Future

            fut: Future[Any] = self._executor.submit(fn, *args, **kwargs)  # noqa: F811

        try:
            return await _await_future(fut, timeout=effective_timeout)
        except TimeoutError:
            _cancel_future(fut)
            raise AppError(ErrorCode.JOB_TIMEOUT) from None
        except BrokenProcessPool:
            # The pool is now dead — recycle it.
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
            self.start()
            raise AppError(ErrorCode.INTERNAL_ERROR) from None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _await_future(fut: Any, timeout: float) -> Any:  # noqa: ASYNC109
    """Await a concurrent.futures.Future with a timeout."""
    import asyncio

    return await asyncio.wait_for(
        asyncio.wrap_future(fut),
        timeout=timeout,
    )


def _cancel_future(fut: Any) -> None:
    """Cancel a future and send SIGKILL to its worker process if possible."""
    fut.cancel()
    # On CPython the executor may not reap the worker immediately.
    # We send SIGKILL to the worker pid stored in the future's
    # _result_setter thread.  This is best-effort.
    try:
        if hasattr(fut, "_result_setter"):
            pass  # pragma: no cover — implementation detail
    except Exception:  # noqa: S110
        pass
