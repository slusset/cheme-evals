"""Script-backed adapters for the eval runner ports."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cheme_evals.application.eval_runner import EvalRunnerDependencies
from cheme_evals.application.fixtures import (
    load_fixture as load_fixture_service,
)
from cheme_evals.application.prompts import (
    build_system_prompt as build_system_prompt_service,
    build_user_prompt as build_user_prompt_service,
)
from cheme_evals.application.runtime import (
    call_agent as call_agent_service,
    save_mock as save_mock_service,
)
from cheme_evals.application.scoring import (
    assemble_result as assemble_result_service,
    score_outputs as score_outputs_service,
    score_reasoning as score_reasoning_service,
    score_tool_proposals as score_tool_proposals_service,
)


@dataclass
class ScriptRuntimeAdapterConfig:
    """Configuration for the runtime metadata adapter."""

    new_run_id_fn: Callable[[], str]
    get_git_sha_fn: Callable[[], str]
    judge_default_model: str


@dataclass
class ScriptRuntimeAdapter:
    """Runtime metadata adapter backed by injected functions."""

    config: ScriptRuntimeAdapterConfig

    def new_run_id(self) -> str:
        return self.config.new_run_id_fn()

    def get_git_sha(self) -> str:
        return self.config.get_git_sha_fn()

    @property
    def judge_default_model(self) -> str:
        return self.config.judge_default_model


@dataclass
class ScriptFixtureAdapterConfig:
    """Configuration for the fixture loading adapter."""

    pass


@dataclass
class ScriptFixtureAdapter:
    """Fixture loading adapter backed by injected functions."""

    config: ScriptFixtureAdapterConfig

    def load_fixture(self, path: str) -> dict:
        return load_fixture_service(path)


@dataclass
class ScriptPromptAdapterConfig:
    """Configuration for the prompt construction adapter."""

    skills_dir: Path


@dataclass
class ScriptPromptAdapter:
    """Prompt construction adapter backed by injected functions."""

    config: ScriptPromptAdapterConfig

    def build_system_prompt(self, fixture: dict, layer: int = 1) -> str:
        return build_system_prompt_service(
            fixture,
            layer=layer,
            skills_dir=self.config.skills_dir,
        )

    def build_user_prompt(self, fixture: dict, layer: int = 1) -> str:
        return build_user_prompt_service(fixture, layer=layer)


@dataclass
class ScriptAgentAdapterConfig:
    """Configuration for the agent invocation adapter."""

    resolve_provider_fn: Callable[[str | None], str]
    providers: dict
    get_api_key_fn: Callable[[str], str]
    anthropic_tool_loop_fn: Callable[..., dict]
    mocks_dir: Path


@dataclass
class ScriptAgentAdapter:
    """Agent invocation adapter backed by injected functions."""

    config: ScriptAgentAdapterConfig

    def call_agent(
        self,
        system_prompt: str,
        user_prompt: str,
        mock_path: str = None,
        provider_name: str = None,
        model: str = None,
        layer: int = 1,
    ) -> dict:
        return call_agent_service(
            system_prompt,
            user_prompt,
            mock_path,
            provider_name=provider_name,
            model=model,
            layer=layer,
            resolve_provider_fn=self.config.resolve_provider_fn,
            providers=self.config.providers,
            get_api_key_fn=self.config.get_api_key_fn,
            anthropic_tool_loop_fn=self.config.anthropic_tool_loop_fn,
        )

    def save_mock(self, response: dict, fixture_id: str) -> None:
        save_mock_service(response, fixture_id, mocks_dir=self.config.mocks_dir)


@dataclass
class ScriptScoringAdapterConfig:
    """Configuration for the scoring adapter."""

    llm_judge_fn: Callable[..., dict]
    get_git_sha_fn: Callable[[], str]


@dataclass
class ScriptScoringAdapter:
    """Scoring and result assembly adapter backed by injected functions."""

    config: ScriptScoringAdapterConfig

    def score_outputs(self, actual: dict, expected: dict, tolerances: dict) -> dict:
        return score_outputs_service(actual, expected, tolerances)

    def score_reasoning(
        self,
        response: dict,
        fixture: dict,
        use_judge: bool = False,
        judge_provider: str = "anthropic",
        judge_model: str = None,
    ) -> dict:
        return score_reasoning_service(
            response,
            fixture,
            use_judge=use_judge,
            judge_provider=judge_provider,
            judge_model=judge_model,
            llm_judge_fn=self.config.llm_judge_fn,
        )

    def score_tool_proposals(self, response: dict, fixture: dict) -> dict:
        return score_tool_proposals_service(response, fixture)

    def assemble_result(
        self,
        fixture: dict,
        response: dict,
        output_scores: dict,
        reasoning_scores: dict,
        proposal_scores: dict = None,
        layer: int = 1,
    ) -> dict:
        return assemble_result_service(
            fixture,
            response,
            output_scores,
            reasoning_scores,
            proposal_scores,
            layer=layer,
            git_sha=self.config.get_git_sha_fn(),
        )


@dataclass
class ScriptPresenterAdapterConfig:
    """Configuration for the presenter adapter."""

    print_results_fn: Callable[[dict], None]


@dataclass
class ScriptPresenterAdapter:
    """Output rendering adapter backed by injected functions."""

    config: ScriptPresenterAdapterConfig

    def print_results(self, result: dict) -> None:
        self.config.print_results_fn(result)


@dataclass
class ScriptTraceAdapterConfig:
    """Configuration for the trace storage adapter."""

    append_trace_event_fn: Callable[[str, str, dict, int], int]
    get_trace_path_fn: Callable[[str], Path]


@dataclass
class ScriptTraceAdapter:
    """Trace storage adapter backed by injected functions."""

    config: ScriptTraceAdapterConfig

    def append_trace_event(self, run_id: str, event_type: str, payload: dict, sequence: int) -> int:
        return self.config.append_trace_event_fn(run_id, event_type, payload, sequence)

    def get_trace_path(self, run_id: str) -> Path:
        return self.config.get_trace_path_fn(run_id)


@dataclass
class ScriptArtifactAdapterConfig:
    """Configuration for the artifact registry adapter."""

    record_artifact_fn: Callable[..., dict]


@dataclass
class ScriptArtifactAdapter:
    """Artifact registry adapter backed by injected functions."""

    config: ScriptArtifactAdapterConfig

    def record_artifact(
        self,
        *,
        run_id: str,
        fixture: dict,
        artifact_type: str,
        proposal: dict,
        git_sha: str,
    ) -> dict:
        return self.config.record_artifact_fn(
            run_id=run_id,
            fixture=fixture,
            artifact_type=artifact_type,
            proposal=proposal,
            git_sha=git_sha,
        )


@dataclass
class ScriptArchiveAdapterConfig:
    """Configuration for the archive ledger adapter."""

    append_archive_record_fn: Callable[[str, str, dict], dict]


@dataclass
class ScriptArchiveAdapter:
    """Archive ledger adapter backed by injected functions."""

    config: ScriptArchiveAdapterConfig

    def append_archive_record(self, record_type: str, record_id: str, payload: dict) -> dict:
        return self.config.append_archive_record_fn(record_type, record_id, payload)


@dataclass
class ScriptResultStoreAdapterConfig:
    """Configuration for the result storage adapter."""

    write_result_fn: Callable[[Path, str, dict], Path]
    append_jsonl_record_fn: Callable[[Path, dict], dict]
    read_jsonl_records_fn: Callable[[Path], list[dict]]


@dataclass
class ScriptResultStoreAdapter:
    """Result storage adapter backed by injected functions."""

    config: ScriptResultStoreAdapterConfig

    def write_result(self, results_dir: Path, filename: str, result: dict) -> Path:
        return self.config.write_result_fn(results_dir, filename, result)

    def append_jsonl_record(self, log_path: Path, entry: dict) -> dict:
        return self.config.append_jsonl_record_fn(log_path, entry)

    def read_jsonl_records(self, log_path: Path) -> list[dict]:
        return self.config.read_jsonl_records_fn(log_path)


@dataclass
class ScriptEvalRunnerAdapterConfig:
    """Top-level configuration for building script-backed eval runner ports."""

    runtime: ScriptRuntimeAdapterConfig
    fixtures: ScriptFixtureAdapterConfig
    prompts: ScriptPromptAdapterConfig
    agent: ScriptAgentAdapterConfig
    scoring: ScriptScoringAdapterConfig
    presenter: ScriptPresenterAdapterConfig
    traces: ScriptTraceAdapterConfig
    artifacts: ScriptArtifactAdapterConfig
    archive: ScriptArchiveAdapterConfig
    results: ScriptResultStoreAdapterConfig


def build_script_eval_runner_dependencies(
    config: ScriptEvalRunnerAdapterConfig,
) -> EvalRunnerDependencies:
    """Build the script-backed dependency bundle for the eval runner."""

    return EvalRunnerDependencies(
        runtime=ScriptRuntimeAdapter(config.runtime),
        fixtures=ScriptFixtureAdapter(config.fixtures),
        prompts=ScriptPromptAdapter(config.prompts),
        agent=ScriptAgentAdapter(config.agent),
        scoring=ScriptScoringAdapter(config.scoring),
        presenter=ScriptPresenterAdapter(config.presenter),
        traces=ScriptTraceAdapter(config.traces),
        artifacts=ScriptArtifactAdapter(config.artifacts),
        archive=ScriptArchiveAdapter(config.archive),
        results=ScriptResultStoreAdapter(config.results),
    )
