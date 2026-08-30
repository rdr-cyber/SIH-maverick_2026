"""Task backend adapter layer.

Defines the ``TaskBackend`` protocol for background work, plus two
concrete implementations:

* ``LocalTaskRunner`` — executes tasks in-process (``APP_MODE=local``).
* ``CeleryTaskRunner`` — delegates to Celery + Redis (``APP_MODE=production``).

The factory ``get_task_backend()`` returns the adapter that matches the
current ``settings.task_backend``.  Business logic depends on the protocol,
never on a concrete runner.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Literal, Protocol, runtime_checkable

from .config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class TaskHandle(Protocol):
    """Opaque handle returned when a task is submitted."""

    @property
    def task_id(self) -> str: ...

    @property
    def status(self) -> str: ...

    def get_result(self, timeout: float | None = None) -> Any: ...


@runtime_checkable
class TaskBackend(Protocol):
    """Minimal contract every task adapter must satisfy."""

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        task_id: str | None = None,
        queue: str = "default",
        **kwargs: Any,
    ) -> TaskHandle:
        """Submit *fn* for background execution.  Returns a handle."""
        ...

    def is_available(self) -> bool:
        """Quick liveness check (e.g. ping Redis)."""
        ...


# ---------------------------------------------------------------------------
# Local implementation (direct execution, local mode)
# ---------------------------------------------------------------------------

class _LocalHandle:
    """Synchronous handle — task runs in a thread pool."""

    def __init__(
        self,
        task_id: str,
        future: Any,
    ) -> None:
        self._task_id = task_id
        self._future = future

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def status(self) -> str:
        if self._future.cancelled():
            return "REVOKED"
        if self._future.done():
            exc = self._future.exception()
            if exc is not None:
                return "FAILURE"
            return "SUCCESS"
        return "PENDING"

    def get_result(self, timeout: float | None = None) -> Any:
        return self._future.result(timeout=timeout)


class LocalTaskRunner:
    """Execute tasks directly in a thread pool.

    Used in ``APP_MODE=local`` when Celery/Redis are not available.
    Tasks run in background threads so the API stays responsive.
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._counter = 0

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        task_id: str | None = None,
        queue: str = "default",
        **kwargs: Any,
    ) -> _LocalHandle:
        self._counter += 1
        tid = task_id or f"local-{self._counter}-{int(time.time())}"
        future = self._pool.submit(fn, *args, **kwargs)
        log.debug("task %s submitted to local runner", tid)
        return _LocalHandle(tid, future)

    def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Celery implementation (production mode) — stub with import guard
# ---------------------------------------------------------------------------

class _CeleryHandle:
    """Wraps an ``AsyncResult`` from Celery."""

    def __init__(self, async_result: Any) -> None:
        self._result = async_result

    @property
    def task_id(self) -> str:
        return str(self._result.id)

    @property
    def status(self) -> str:
        return self._result.status

    def get_result(self, timeout: float | None = None) -> Any:
        return self._result.get(timeout=timeout)


class CeleryTaskRunner:
    """Delegate tasks to Celery + Redis broker.

    Requires ``celery`` and ``redis`` Python packages.
    The Celery app is ``app.workers.celery_app`` (created in Phase 11).
    """

    def __init__(self) -> None:
        self._celery_app: Any = None

    def _get_app(self) -> Any:
        if self._celery_app is not None:
            return self._celery_app
        try:
            from app.workers.celery_app import celery_app  # type: ignore[import-not-found]
            self._celery_app = celery_app
            return self._celery_app
        except ImportError:
            raise RuntimeError(
                "Celery app not found.  "
                "Ensure app.workers.celery_app exists and celery + redis "
                "are installed."
            )

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        task_id: str | None = None,
        queue: str = "default",
        **kwargs: Any,
    ) -> _CeleryHandle:
        app = self._get_app()
        # fn must be a registered Celery task for this to work
        result = app.send_task(
            fn.name if hasattr(fn, "name") else str(fn),
            args=args,
            kwargs=kwargs,
            task_id=task_id,
            queue=queue,
        )
        log.debug("task %s submitted to celery queue=%s", result.id, queue)
        return _CeleryHandle(result)

    def is_available(self) -> bool:
        try:
            app = self._get_app()
            inspect = app.control.inspect(timeout=2.0)
            workers = inspect.ping()
            return bool(workers)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_task_instance: TaskBackend | None = None


def get_task_backend() -> TaskBackend:
    """Return the configured task adapter (singleton per process)."""
    global _task_instance
    if _task_instance is not None:
        return _task_instance

    backend = settings.task_backend
    if backend == "celery":
        _task_instance = CeleryTaskRunner()
        log.info("task adapter: celery")
    else:
        _task_instance = LocalTaskRunner()
        log.info("task adapter: local (thread pool)")

    return _task_instance


def reset_task_backend() -> None:
    """Reset singleton — used by tests."""
    global _task_instance
    _task_instance = None
