"""Unit tests of `step_failure`, the errors-entry builder and the AI gateway's dependency naming
([Job queue](/architecture/services/worker.md#job-queue) Retries;
[Conventions](/architecture/interfaces.md#conventions))."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from leadradar.ai.errors import BudgetExhausted, UpstreamUnavailable
from leadradar.ai.fixtures import FixtureMissing
from leadradar.ai.gateway import _dependency
from leadradar.core.enums import AiRole, Dependency, PipelineRunStage
from leadradar.worker.queue import build_run_error
from leadradar.worker.steps import step_failure

pytestmark = pytest.mark.unit


class TestStepFailure:
    @pytest.mark.parametrize(
        ("exception", "expected_code", "expected_dependency"),
        [
            pytest.param(
                UpstreamUnavailable(Dependency.CLASSIFIER, "ERROR", "boom"),
                "UPSTREAM_UNAVAILABLE",
                Dependency.CLASSIFIER,
                id="an_unavailable_classifier_maps_to_upstream_unavailable",
            ),
            pytest.param(
                UpstreamUnavailable(Dependency.LLM, "TIMEOUT", "boom"),
                "UPSTREAM_UNAVAILABLE",
                Dependency.LLM,
                id="an_unavailable_llm_maps_to_upstream_unavailable",
            ),
            pytest.param(
                UpstreamUnavailable(Dependency.EMBEDDER, "ERROR", "boom"),
                "UPSTREAM_UNAVAILABLE",
                Dependency.EMBEDDER,
                id="an_unavailable_embedder_maps_to_upstream_unavailable",
            ),
            pytest.param(
                UpstreamUnavailable(Dependency.LLM, "NOT_CONFIGURED", "unset"),
                "NOT_CONFIGURED",
                Dependency.LLM,
                id="not_configured_keeps_its_dependency",
            ),
            pytest.param(
                FixtureMissing("openrouter", "key"),
                "FIXTURE_MISSING",
                None,
                id="a_missing_recording_has_no_dependency",
            ),
            pytest.param(
                BudgetExhausted(datetime(2026, 9, 27, tzinfo=UTC)),
                "BUDGET_EXHAUSTED",
                None,
                id="a_budget_stop_has_no_dependency",
            ),
        ],
    )
    def test_step_failure(
        self,
        exception: UpstreamUnavailable | BudgetExhausted | FixtureMissing,
        expected_code: str,
        expected_dependency: Dependency | None,
    ) -> None:
        failure = step_failure(exception)
        assert failure.code == expected_code
        assert failure.dependency == expected_dependency


class TestBuildRunError:
    def test_absent_keys_are_absent_never_null(self) -> None:
        error = build_run_error(stage=PipelineRunStage.SCORE, code="INTERNAL", message="boom")
        assert error == {"stage": "SCORE", "code": "INTERNAL", "message": "boom"}

    def test_plugin_code_present_only_when_given(self) -> None:
        error = build_run_error(
            stage=PipelineRunStage.FETCH,
            code="UPSTREAM_UNAVAILABLE",
            message="x",
            plugin_code="GDELT",
        )
        assert error["plugin_code"] == "GDELT"
        assert "dependency" not in error

    def test_dependency_present_only_when_given(self) -> None:
        error = build_run_error(
            stage=PipelineRunStage.EVIDENCE,
            code="UPSTREAM_UNAVAILABLE",
            message="x",
            dependency=Dependency.LLM,
        )
        assert error["dependency"] == "LLM"
        assert "plugin_code" not in error


class TestGatewayDependencyNaming:
    def test_classifier_role_names_classifier(self) -> None:
        assert _dependency(AiRole.CLASSIFIER) == Dependency.CLASSIFIER

    @pytest.mark.parametrize("role", [AiRole.ESCALATION, AiRole.EVIDENCE, AiRole.OUTREACH])
    def test_every_other_role_names_llm(self, role: AiRole) -> None:
        assert _dependency(role) == Dependency.LLM
