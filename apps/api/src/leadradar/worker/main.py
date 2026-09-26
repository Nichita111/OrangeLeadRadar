"""Entry point `leadradar-worker` ([Runtime](/architecture/services/worker.md#runtime)).

Starts `WORKER_CONCURRENCY` job loops from `queue.py` and waits for a stop signal.
Signal handling (SIGTERM/SIGINT) cancels all loops gracefully.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import uuid

from leadradar.db.session import build_engine
from leadradar.logs import configure_json_logging
from leadradar.worker.queue import run_job_loop
from leadradar.worker.settings import WorkerSettings

logger = logging.getLogger(__name__)


async def _run(settings: WorkerSettings) -> None:
    engine = build_engine(settings.database_url.get_secret_value())
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle_signal(received: signal.Signals) -> None:
        logger.info("Received %s; stopping", received.name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    tasks = [
        asyncio.create_task(
            run_job_loop(engine, settings, f"worker-{uuid.uuid4().hex[:8]}")
        )
        for _ in range(settings.worker_concurrency)
    ]

    await stop_event.wait()

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await engine.dispose()
    logger.info("Worker stopped")


def run() -> None:
    """`leadradar-worker`: starts job loops and blocks until a stop signal."""
    settings = WorkerSettings()
    configure_json_logging(settings.log_level)
    logger.info("Worker started")
    asyncio.run(_run(settings))


if __name__ == "__main__":
    run()
