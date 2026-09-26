"""[worker Job queue](/architecture/services/worker.md#job-queue) priority table, as one pure
function: the api's enqueueing (`runs.enqueue`) and the worker's own claiming share this one
fact instead of each restating it."""

from __future__ import annotations

from leadradar.core.enums import PipelineRunKind, PipelineRunTrigger

# Kinds whose priority does not depend on the trigger: every row of the table names the kind
# alone (`RECLASSIFY`, `DISCOVERY`, `EVALUATION`).
_KIND_ONLY_PRIORITIES: dict[PipelineRunKind, int] = {
    PipelineRunKind.RECLASSIFY: 3,
    PipelineRunKind.DISCOVERY: 7,
    PipelineRunKind.EVALUATION: 7,
}

# Kinds whose priority depends on the trigger too (`RESCORE`, `ACCOUNT_REFRESH`).
_KIND_TRIGGER_PRIORITIES: dict[tuple[PipelineRunKind, PipelineRunTrigger], int] = {
    (PipelineRunKind.RESCORE, PipelineRunTrigger.FEEDBACK): 0,
    (PipelineRunKind.RESCORE, PipelineRunTrigger.OVERRIDE): 0,
    (PipelineRunKind.RESCORE, PipelineRunTrigger.ACCOUNT_CHANGE): 0,
    (PipelineRunKind.RESCORE, PipelineRunTrigger.SCORING_ACTIVATION): 3,
    (PipelineRunKind.ACCOUNT_REFRESH, PipelineRunTrigger.USER): 1,
    (PipelineRunKind.ACCOUNT_REFRESH, PipelineRunTrigger.SCHEDULE): 5,
}


class UnknownJobPriority(Exception):
    """No row of [worker Job queue](/architecture/services/worker.md#job-queue) lists this kind
    and trigger; there is no default priority."""


def job_priority(kind: PipelineRunKind, trigger: PipelineRunTrigger) -> int:
    """The priority a `job` of a run of `kind`, triggered by `trigger`, is enqueued at."""
    if kind in _KIND_ONLY_PRIORITIES:
        return _KIND_ONLY_PRIORITIES[kind]
    pair = (kind, trigger)
    if pair in _KIND_TRIGGER_PRIORITIES:
        return _KIND_TRIGGER_PRIORITIES[pair]
    raise UnknownJobPriority(f"No job-queue priority for {kind} triggered by {trigger}.")
