"""Entry point `leadradar-worker` ([Runtime](/architecture/services/worker.md#runtime)).

This task's worker is its entry point and nothing else: it starts, configures JSON logging and
waits for `SIGTERM` or `SIGINT`, then exits `0`. The
[job queue](/architecture/services/worker.md#job-queue) loop arrives with the first task that
enqueues a job (`S-PIP-01`).
"""

from __future__ import annotations

import asyncio
import logging
import signal

from leadradar.logs import configure_json_logging
from leadradar.worker.settings import WorkerSettings

logger = logging.getLogger(__name__)


async def _wait_for_stop_signal() -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal(received: signal.Signals) -> None:
        logger.info("Received %s; stopping", received.name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    await stop_event.wait()


def run() -> None:
    """`leadradar-worker`: blocks until a stop signal, then exits `0`."""
    settings = WorkerSettings()
    configure_json_logging(settings.log_level)
    logger.info("Worker started")
    asyncio.run(_wait_for_stop_signal())
    logger.info("Worker stopped")


if __name__ == "__main__":
    run()
