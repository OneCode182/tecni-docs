"""
Scheduler Service Module
========================

This module provides the SchedulerService for managing scheduled tasks using APScheduler.
It handles task scheduling, execution monitoring, and lifecycle management.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict

from apscheduler import events  # type: ignore
from apscheduler.events import JobExecutionEvent  # type: ignore
from apscheduler.executors.asyncio import AsyncIOExecutor  # type: ignore
from apscheduler.job import Job  # type: ignore
from apscheduler.jobstores.memory import MemoryJobStore  # type: ignore
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore

from biostar_adapter.common.utility import LoggerMixin


class SchedulerService(LoggerMixin):
    """Service for managing scheduled tasks using APScheduler."""

    def __init__(self, *, logger: logging.Logger, timezone: str = "UTC") -> None:
        self._build_logger(logger=logger)

        # Configure jobstores and executors
        jobstores = {"default": MemoryJobStore()}
        executors = {"default": AsyncIOExecutor()}

        job_defaults = {"coalesce": False, "max_instances": 3}

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=timezone,
        )

        # Add event listeners
        self._scheduler.add_listener(  # type: ignore
            self._job_executed, events.EVENT_JOB_EXECUTED | events.EVENT_JOB_ERROR
        )

    async def start(self) -> None:
        """Start the scheduler."""
        self._scheduler.start()  # type: ignore
        self._logger.info("Scheduler service started")

    async def shutdown(self) -> None:
        """Shutdown the scheduler."""
        self._scheduler.shutdown(wait=True)  # type: ignore
        self._logger.info("Scheduler service stopped")

    def schedule_task(
        self,
        func: Callable[..., Any],
        run_date: datetime,
        args: tuple[Any, ...] = (),
        kwargs: Dict[str, Any] = {},
        job_id: str | None = None,
    ) -> str:
        """Schedule a task to run at a specific datetime."""

        job: Job = self._scheduler.add_job(  # type: ignore
            func=func,
            trigger="date",
            run_date=run_date,
            args=args,
            kwargs=kwargs,
            id=job_id,
        )

        remaining_seconds = (run_date - datetime.now(run_date.tzinfo)).total_seconds()
        self._logger.debug(
            f"Scheduled task {job.id} to run at {run_date} (in {remaining_seconds:.2f} seconds)"  # type: ignore
        )
        self._logger.debug(job)
        return str(job.id)  # type: ignore

    def cancel_task(self, job_id: str) -> bool:
        """Cancel a scheduled task."""
        try:
            self._scheduler.remove_job(job_id)  # type: ignore
            self._logger.debug(f"Cancelled task {job_id}")
            return True
        except Exception as e:
            self._logger.warning(f"Failed to cancel task {job_id}: {e}")
            return False

    def _job_executed(self, event: JobExecutionEvent) -> None:  # type: ignore
        """Handle job execution events."""
        if event.exception:  # type: ignore
            self._logger.error(
                f"Task {event.job_id} failed with exception: {event.exception}"  # type: ignore
            )
        else:
            self._logger.debug(f"Task {event.job_id} executed successfully")  # type: ignore
