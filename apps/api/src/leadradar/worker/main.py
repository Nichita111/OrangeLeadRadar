"""Entry point `leadradar-worker` ([Runtime](/architecture/services/worker.md#runtime)): starts
`WORKER_CONCURRENCY` [job loops](/architecture/services/worker.md#job-queue) and the
[scheduler loop](/architecture/services/worker.md#scheduler-and-housekeeping) over one database
engine, and on `SIGTERM` or `SIGINT` lets each finish the job or tick in hand, then exits `0`."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket

from sqlalchemy.ext.asyncio import async_sessionmaker

from leadradar.clock import build_clock
from leadradar.db.session import build_engine
from leadradar.logs import configure_json_logging
from leadradar.worker.loop import run_job_loop
from leadradar.worker.scheduler import run_scheduler_loop
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import STEP_HANDLERS

logger = logging.getLogger(__name__)


async def _serve(settings: WorkerSettings) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _handle_signal(received: signal.Signals) -> None:
        logger.info("Received %s; stopping", received.name)
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    engine = build_engine(settings.database_url.get_secret_value())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    clock = build_clock(settings)
    instance = f"{socket.gethostname()}:{os.getpid()}"
    try:
        async with asyncio.TaskGroup() as loops:
            for index in range(settings.worker_concurrency):
                loops.create_task(
                    run_job_loop(
                        session_factory,
                        handlers=STEP_HANDLERS,
                        settings=settings,
                        clock=clock,
                        worker_id=f"{instance}:{index}",
                        stop=stop,
                    )
                )
            loops.create_task(
                run_scheduler_loop(session_factory, clock=clock, settings=settings, stop=stop)
            )
    finally:
        await engine.dispose()


def run() -> None:
    """`leadradar-worker`: runs the job loops until a stop signal, then exits `0`."""
    settings = WorkerSettings()
    configure_json_logging(settings.log_level)
    logger.info("Worker started")
    asyncio.run(_serve(settings))
    logger.info("Worker stopped")


if __name__ == "__main__":
    run()
