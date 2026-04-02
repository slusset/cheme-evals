"""
Direct application-layer tests.

These tests target the services under src/cheme_evals/application directly,
without going through the legacy run_eval.py shell.
"""
import json
import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from cheme_evals.application.eval_runner import (
    EvalRunnerDependencies,
    compare_experiments,
    log_experiment,
    run_fixture,
)
from cheme_evals.application.presentation import (
    load_trace_events,
    print_results,
    print_trace_summary,
)
from cheme_evals.application.runtime import call_agent, save_mock
from cheme_evals.domain.config import HarnessPaths


class FakeRuntime:
    judge_default_model = "judge-default"

    def new_run_id(self):
        return "run-123"

    def get_git_sha(self):
        return "deadbee"


class FakeFixtures:
    def __init__(self, fixture):
        self.fixture = fixture

    def load_fixture(self, path: str):
        return self.fixture


class FakePrompts:
    def build_system_prompt(self, fixture: dict, layer: int = 1):
        return f"system-layer-{layer}"

    def build_user_prompt(self, fixture: dict, layer: int = 1):
        return f"user-layer-{layer}"


class FakeAgent:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.saved = []

    def call_agent(self, system_prompt, user_prompt, mock_path=None, provider_name=None, model=None, layer=1):
        self.calls.append({
            "system": system_prompt,
            "user": user_prompt,
            "mock_path": mock_path,
            "provider_name": provider_name,
            "model": model,
            "layer": layer,
        })
        return dict(self.response)

    def save_mock(self, response: dict, fixture_id: str):
        self.saved.append((fixture_id, response))


class FakeScoring:
    def score_outputs(self, actual, expected, tolerances):
        return {
            "output_scores": {"x": {"status": "PASS"}},
            "numeric_score": 1,
            "numeric_possible": 1,
            "numeric_pct": 100.0,
        }

    def score_reasoning(self, response, fixture, use_judge=True, judge_provider="anthropic", judge_model=None):
        return {
            "reasoning_checkpoints": [],
            "reasoning_score_pct": 80.0,
            "judge_method": "heuristic",
            "score_reliability": "rough_heuristic",
        }

    def score_tool_proposals(self, response, fixture):
        if response.get("_meta", {}).get("tool_proposals"):
            return {
                "proposal_score": 1,
                "proposal_possible": 1,
                "proposal_score_pct": 100.0,
            }
        return {
            "proposal_score": 0,
            "proposal_possible": 0,
            "proposal_score_pct": 0,
        }

    def assemble_result(self, fixture, response, output_scores, reasoning_scores, proposal_scores=None, layer=1):
        return {
            "run_id": response["_meta"]["run_id"],
            "fixture_id": fixture["id"],
            "fixture_version": fixture["version"],
            "layer": layer,
            "agent_meta": response["_meta"],
            "scores": {
                "numeric": output_scores,
                "reasoning": reasoning_scores,
                "tool_proposals": proposal_scores or {},
                "overall_pct": 88.0,
            },
            "agent_response": {"confidence": 0.9},
            "tool_proposals": response["_meta"].get("tool_proposals", []),
            "artifacts": response["_meta"].get("artifacts", []),
        }


class FakePresenter:
    def __init__(self):
        self.presented = []

    def print_results(self, result):
        self.presented.append(result)


class FakeTraces:
    def __init__(self, traces_dir: Path):
        self.traces_dir = traces_dir
        self.events = []

    def append_trace_event(self, run_id, event_type, payload, sequence):
        self.events.append({
            "run_id": run_id,
            "type": event_type,
            "payload": payload,
            "sequence": sequence,
        })
        return sequence + 1

    def get_trace_path(self, run_id):
        return self.traces_dir / f"{run_id}.jsonl"


class FakeArtifacts:
    def __init__(self):
        self.created = []

    def record_artifact(self, *, run_id, fixture, artifact_type, proposal, git_sha):
        artifact = {
            "artifact_id": "artifact-1",
            "artifact_type": artifact_type,
            "artifact_path": "/tmp/artifact-1.json",
            "source_run_id": run_id,
            "proposal": proposal,
        }
        self.created.append(artifact)
        return artifact


class FakeArchive:
    def __init__(self):
        self.records = []

    def append_archive_record(self, record_type, record_id, payload):
        record = {
            "record_type": record_type,
            "record_id": record_id,
            "payload": payload,
        }
        self.records.append(record)
        return record


class FakeResults:
    def __init__(self, result_path: Path):
        self.result_path = result_path
        self.written = []
        self.jsonl = []

    def write_result(self, results_dir: Path, filename: str, result: dict):
        path = results_dir / filename
        self.written.append((path, result))
        return path

    def append_jsonl_record(self, log_path: Path, entry: dict):
        self.jsonl.append((log_path, entry))
        return entry

    def read_jsonl_records(self, log_path: Path):
        return [entry for entry_log_path, entry in self.jsonl if entry_log_path == log_path]


def build_paths(tmp_path: Path) -> HarnessPaths:
    return HarnessPaths.from_root(tmp_path)


class TestApplicationRuntime:

    def test_call_agent_replays_mock_from_file(self, tmp_path):
        mock_path = tmp_path / "response.json"
        mock_path.write_text(json.dumps({"outputs": {"x": {"value": 1, "unit": "m"}}}))

        result = call_agent(
            "system",
            "user",
            str(mock_path),
            resolve_provider_fn=lambda name: name or "anthropic",
            providers={},
            get_api_key_fn=lambda provider: "key",
            anthropic_tool_loop_fn=lambda **kwargs: {},
        )

        assert result["outputs"]["x"]["value"] == 1

    def test_call_agent_live_path_parses_json_and_meta(self):
        result = call_agent(
            "system",
            "user",
            provider_name="anthropic",
            model="fake-model",
            layer=1,
            resolve_provider_fn=lambda name: name or "anthropic",
            providers={
                "anthropic": {
                    "default_model": "default-model",
                    "call": lambda **kwargs: {
                        "text": json.dumps({"outputs": {"x": {"value": 2, "unit": "m"}}}),
                        "model": "fake-model",
                        "input_tokens": 11,
                        "output_tokens": 7,
                    },
                }
            },
            get_api_key_fn=lambda provider: "key",
            anthropic_tool_loop_fn=lambda **kwargs: {},
        )

        assert result["outputs"]["x"]["value"] == 2
        assert result["_meta"]["provider"] == "anthropic"
        assert result["_meta"]["model"] == "fake-model"

    def test_save_mock_writes_agent_response_file(self, tmp_path):
        saved = save_mock({"outputs": {}}, "fixture-1", mocks_dir=tmp_path)
        assert saved.exists()
        assert saved.name == "fixture-1.json"


class TestApplicationEvalRunner:

    def test_run_fixture_orchestrates_trace_result_and_archive(self, tmp_path):
        fixture = {
            "id": "fixture-1",
            "version": "1.0.0",
            "problem": {"statement": "Compute x", "task": "Return x"},
            "inputs": {"feed": {"value": 1, "unit": "mol", "input_class": "problem_data"}},
            "expected_outputs": {"x": {"value": 1, "unit": "mol"}},
            "acceptance_criteria": {"tolerances": {}},
        }
        response = {
            "outputs": {"x": {"value": 1, "unit": "mol"}},
            "_meta": {
                "provider": "anthropic",
                "model": "fake-model",
                "tool_proposals": [
                    {"tool_name": "steam_table_lookup", "priority": "blocking", "reason": "need props"}
                ],
            },
        }

        traces = FakeTraces(tmp_path / "traces")
        artifacts = FakeArtifacts()
        archive = FakeArchive()
        results = FakeResults(tmp_path / "results" / "fixture-1.json")
        presenter = FakePresenter()
        deps = EvalRunnerDependencies(
            runtime=FakeRuntime(),
            fixtures=FakeFixtures(fixture),
            prompts=FakePrompts(),
            agent=FakeAgent(response),
            scoring=FakeScoring(),
            presenter=presenter,
            traces=traces,
            artifacts=artifacts,
            archive=archive,
            results=results,
        )

        result = run_fixture(
            paths=build_paths(tmp_path),
            deps=deps,
            fixture_path="fixture.json",
            provider_name="anthropic",
            model="fake-model",
            layer=3,
        )

        assert result["run_id"] == "run-123"
        assert presenter.presented[0]["fixture_id"] == "fixture-1"
        assert [event["type"] for event in traces.events] == [
            "run_started",
            "prompt_built",
            "agent_call_started",
            "agent_response_received",
            "artifact_proposed",
            "scores_computed",
            "result_written",
            "run_completed",
        ]
        assert archive.records[-1]["record_type"] == "run"
        assert len(artifacts.created) == 1
        assert results.written

    def test_log_and_compare_experiments_work_with_result_store_port(self, tmp_path, capsys):
        results_store = FakeResults(tmp_path / "results" / "fixture-1.json")
        deps = EvalRunnerDependencies(
            runtime=FakeRuntime(),
            fixtures=FakeFixtures({}),
            prompts=FakePrompts(),
            agent=FakeAgent({}),
            scoring=FakeScoring(),
            presenter=FakePresenter(),
            traces=FakeTraces(tmp_path / "traces"),
            artifacts=FakeArtifacts(),
            archive=FakeArchive(),
            results=results_store,
        )
        paths = build_paths(tmp_path)
        paths.experiment_log.parent.mkdir(parents=True, exist_ok=True)
        paths.experiment_log.touch()

        first = {
            "fixture_id": "fixture-1",
            "scores": {
                "numeric": {"numeric_pct": 70.0},
                "reasoning": {"reasoning_score_pct": 80.0, "judge_method": "heuristic"},
                "tool_proposals": {"proposal_score_pct": 100.0},
                "overall_pct": 76.0,
            },
            "agent_response": {"confidence": 0.8},
            "agent_meta": {"model": "fake-model"},
        }
        second = {
            "fixture_id": "fixture-1",
            "scores": {
                "numeric": {"numeric_pct": 90.0},
                "reasoning": {"reasoning_score_pct": 95.0, "judge_method": "heuristic"},
                "tool_proposals": {"proposal_score_pct": 100.0},
                "overall_pct": 92.0,
            },
            "agent_response": {"confidence": 0.9},
            "agent_meta": {"model": "fake-model"},
        }

        log_experiment(
            paths=paths,
            deps=deps,
            results=[first],
            tag="baseline",
            layer=1,
            provider_name="anthropic",
            model="fake-model",
        )
        log_experiment(
            paths=paths,
            deps=deps,
            results=[second],
            tag="improved",
            layer=1,
            provider_name="anthropic",
            model="fake-model",
        )

        compare_experiments(paths=paths, deps=deps, last_n=2)
        output = capsys.readouterr().out
        assert "EXPERIMENT COMPARISON" in output
        assert "baseline" in output
        assert "improved" in output
        assert "DIFF" in output


class TestApplicationPresentation:

    def test_print_results_renders_proposal_and_reasoning_sections(self, capsys):
        result = {
            "fixture_id": "fixture-1",
            "fixture_version": "1.0.0",
            "layer": 3,
            "timestamp": "2026-04-01T12:00:00Z",
            "git_sha": "deadbee",
            "scores": {
                "numeric": {
                    "numeric_score": 1,
                    "numeric_possible": 1,
                    "numeric_pct": 100.0,
                    "output_scores": {
                        "x": {"status": "PASS", "expected": 1, "actual": 1}
                    },
                },
                "reasoning": {
                    "reasoning_score_pct": 75.0,
                    "judge_method": "heuristic",
                    "score_notes": "Rough heuristic only.",
                    "reasoning_checkpoints": [],
                    "must_include": [],
                    "must_not_include": [],
                },
                "tool_proposals": {
                    "proposal_possible": 1,
                    "proposal_score_pct": 100.0,
                    "notes": "Correct blocking tool proposal.",
                },
                "overall_pct": 91.0,
            },
            "tool_proposals": [
                {
                    "tool_name": "steam_table_lookup",
                    "priority": "blocking",
                    "reason": "Need saturation data.",
                }
            ],
            "agent_response": {"confidence": 0.9},
        }

        print_results(result)
        output = capsys.readouterr().out

        assert "EVAL: fixture-1 v1.0.0" in output
        assert "REASONING (ROUGH HEURISTIC): 75.0%" in output
        assert "TOOL PROPOSAL QUALITY: 100.0%" in output
        assert "steam_table_lookup" in output

    def test_trace_helpers_load_and_filter_summary(self, tmp_path, capsys):
        trace_path = tmp_path / "run-123.jsonl"
        trace_path.write_text(
            "\n".join(
                [
                    json.dumps({
                        "sequence": 1,
                        "type": "run_started",
                        "timestamp": "2026-04-01T12:00:00Z",
                        "payload": {
                            "fixture_id": "fixture-1",
                            "fixture_version": "1.0.0",
                            "layer": 3,
                            "use_mock": True,
                            "provider_name": "anthropic",
                            "model": "claude",
                        },
                    }),
                    json.dumps({
                        "sequence": 2,
                        "type": "artifact_proposed",
                        "timestamp": "2026-04-01T12:00:01Z",
                        "payload": {
                            "proposal": {"tool_name": "steam_table_lookup"},
                        },
                    }),
                    json.dumps({
                        "sequence": 3,
                        "type": "run_completed",
                        "timestamp": "2026-04-01T12:00:02Z",
                        "payload": {
                            "overall_pct": 90.0,
                            "result_path": "results/fixture-1.json",
                        },
                    }),
                ]
            )
            + "\n"
        )

        events = load_trace_events(trace_path)
        print_trace_summary("run-123", events, event_types=["artifact_proposed"])
        output = capsys.readouterr().out

        assert len(events) == 3
        assert "TRACE SUMMARY: run-123" in output
        assert "Artifacts proposed: 1" in output
        assert "artifact_proposed" in output
        assert "run_started" not in output.split("EVENTS", 1)[1]
