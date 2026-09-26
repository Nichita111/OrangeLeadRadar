"""[Run lifecycle](/architecture/services/worker.md#run-lifecycle) and the fan-out of
[Job queue](/architecture/services/worker.md#job-queue), as pure functions: which stage a claimed
job moves its run to, which job the job loop still owes a run whose jobs are all final, and the
status a finished run ends in. The worker's job loop invokes them; nothing here reads the store."""

from __future__ import annotations

from collections.abc import Collection

from leadradar.core.enums import (
    JobStep,
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    SourcePluginCode,
)

# The first stage each step covers
# ([Run lifecycle](/architecture/services/worker.md#run-lifecycle)).
_FIRST_STAGE_OF_STEP: dict[JobStep, PipelineRunStage] = {
    JobStep.FETCH: PipelineRunStage.FETCH,
    JobStep.DISCOVER: PipelineRunStage.FETCH,
    JobStep.PROCESS: PipelineRunStage.PROCESS,
    JobStep.SIGNAL: PipelineRunStage.TRIAGE,
    JobStep.EVALUATE: PipelineRunStage.CLASSIFY,
    JobStep.SCORE: PipelineRunStage.SCORE,
}

# The step of each kind's final stage: `SCORE`, the last `DISCOVER` or the last `EVALUATE`.
FINAL_STEP: dict[PipelineRunKind, JobStep] = {
    PipelineRunKind.ACCOUNT_REFRESH: JobStep.SCORE,
    PipelineRunKind.RECLASSIFY: JobStep.SCORE,
    PipelineRunKind.RESCORE: JobStep.SCORE,
    PipelineRunKind.DISCOVERY: JobStep.DISCOVER,
    PipelineRunKind.EVALUATION: JobStep.EVALUATE,
}

# Kinds whose `SCORE` job the job loop enqueues when no step of the run did.
_KINDS_OWED_A_SCORE_JOB = frozenset({PipelineRunKind.ACCOUNT_REFRESH, PipelineRunKind.RECLASSIFY})

_STAGE_ORDER = list(PipelineRunStage)


def stage_after_claim(current: PipelineRunStage | None, step: JobStep) -> PipelineRunStage:
    """The run's `stage` once a job of `step` is claimed: the first stage the step covers, never
    an earlier stage than `current`."""
    claimed = _FIRST_STAGE_OF_STEP[step]
    if current is not None and _STAGE_ORDER.index(current) > _STAGE_ORDER.index(claimed):
        return current
    return claimed


def owed_final_job(kind: PipelineRunKind, steps_in_run: Collection[JobStep]) -> JobStep | None:
    """With every job of the run final: the step the job loop must still enqueue — `SCORE` for
    an `ACCOUNT_REFRESH` or `RECLASSIFY` run that has no `SCORE` job — or `None` when the run is
    ready to finish."""
    if kind in _KINDS_OWED_A_SCORE_JOB and JobStep.SCORE not in steps_in_run:
        return JobStep.SCORE
    return None


def run_outcome(
    *, final_stage_failed: bool, has_errors: bool, pending_budget: int
) -> PipelineRunStatus:
    """The final status of a run whose jobs are all final: `FAILED` when its final stage failed
    after its retries; `PARTIAL` when a plug-in or step failed (`errors`) or pairs were left
    waiting (`progress.pending_budget`); `SUCCEEDED` otherwise."""
    if final_stage_failed:
        return PipelineRunStatus.FAILED
    if has_errors or pending_budget > 0:
        return PipelineRunStatus.PARTIAL
    return PipelineRunStatus.SUCCEEDED


def refresh_first_jobs(
    available_plugins: Collection[SourcePluginCode],
) -> list[tuple[JobStep, dict[str, object]]]:
    """The first-stage jobs of an `ACCOUNT_REFRESH`, as `(step, payload)`: one `FETCH` per
    available plug-in, `{plugin_code}`; with none available, its `SCORE` job, `{}`."""
    if not available_plugins:
        return [(JobStep.SCORE, {})]
    order = list(SourcePluginCode)
    return [
        (JobStep.FETCH, {"plugin_code": code.value})
        for code in sorted(available_plugins, key=order.index)
    ]
