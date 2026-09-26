"""Typed failures of a [source plug-in](/architecture/interfaces.md#source-plug-ins) fetch, that
the `FETCH` [step handler](/architecture/services/worker.md#job-queue) maps to a `StepFailed`
error code."""

from __future__ import annotations


class PluginFetchFailed(Exception):
    """The plug-in's provider could not be reached or answered with an error; maps to
    `UPSTREAM_UNAVAILABLE`."""
