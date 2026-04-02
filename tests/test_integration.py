"""
Integration tests for mock replay and Layer 3 tool proposal plumbing.
"""
import json
import sys
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providers
import run_eval


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestMockReplayIntegration:

    def test_run_fixture_with_saved_mock_writes_result(self, monkeypatch, tmp_path):
        traces_dir = tmp_path / "traces"
        artifacts_dir = tmp_path / "artifacts"
        archive_log = tmp_path / "archive.jsonl"
        monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(run_eval, "TRACES_DIR", traces_dir)
        monkeypatch.setattr(run_eval, "ARTIFACTS_DIR", artifacts_dir)
        monkeypatch.setattr(run_eval, "ARCHIVE_LOG", archive_log)
        monkeypatch.setattr(run_eval, "get_git_sha", lambda: "deadbee")

        fixture_path = PROJECT_ROOT / "fixtures" / "flash-distillation-01.json"

        result = run_eval.run_fixture(str(fixture_path), use_mock=True, layer=1, use_judge=False)

        assert result["run_id"]
        assert result["fixture_id"] == "flash-distillation-01"
        assert result["agent_meta"]["provider"] == "anthropic"
        assert result["agent_meta"]["model"] == "claude-sonnet-4-20250514"
        assert result["scores"]["numeric"]["numeric_possible"] == 5

        saved_results = list(tmp_path.glob("flash-distillation-01-L1-deadbee-*.json"))
        assert len(saved_results) == 1

        saved_payload = json.loads(saved_results[0].read_text())
        assert saved_payload["run_id"] == result["run_id"]
        assert saved_payload["fixture_id"] == "flash-distillation-01"
        assert saved_payload["scores"]["numeric"]["numeric_possible"] == 5

        trace_path = traces_dir / f"{result['run_id']}.jsonl"
        assert trace_path.exists()
        events = [json.loads(line) for line in trace_path.read_text().splitlines()]
        assert [event["type"] for event in events] == [
            "run_started",
            "prompt_built",
            "agent_call_started",
            "agent_response_received",
            "scores_computed",
            "result_written",
            "run_completed",
        ]
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        archive_records = [json.loads(line) for line in archive_log.read_text().splitlines()]
        assert archive_records[-1]["record_type"] == "run"
        assert archive_records[-1]["record_id"] == result["run_id"]

    def test_call_agent_with_missing_mock_fails_fast(self):
        missing_mock = PROJECT_ROOT / "mocks" / "agent-responses" / "does-not-exist.json"

        try:
            run_eval.call_agent("system", "user", mock_path=str(missing_mock))
            assert False, "Expected FileNotFoundError for missing mock"
        except FileNotFoundError as exc:
            assert "Requested mock response does not exist" in str(exc)


class TestAnthropicToolLoopIntegration:

    def test_call_anthropic_tool_loop_executes_python_then_returns_final_answer(self, monkeypatch):
        requests = []
        responses = iter([
            {
                "usage": {"input_tokens": 80, "output_tokens": 15},
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_py_1",
                        "name": "python_execute",
                        "input": {
                            "code": "print(373.15)"
                        },
                    }
                ],
                "stop_reason": "tool_use",
                "model": "fake-sonnet",
            },
            {
                "usage": {"input_tokens": 50, "output_tokens": 25},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "reasoning": "Used python to confirm the boiling point value.",
                                "assumptions": ["Ideal behavior"],
                                "method": "python_execute",
                                "calculations": {"boiling_point_K": 373.15},
                                "outputs": {
                                    "boiling_point": {"value": 373.15, "unit": "K"}
                                },
                                "confidence": 0.9,
                                "skill_notes": "",
                            }
                        ),
                    }
                ],
                "stop_reason": "end_turn",
                "model": "fake-sonnet",
            },
        ])

        def fake_post_json(url, headers, body, timeout=120):
            requests.append(body)
            return next(responses)

        monkeypatch.setattr(providers, "_post_json", fake_post_json)

        result = providers.call_anthropic_tool_loop(
            system="system",
            user="user",
            model="fake-sonnet",
            temperature=0,
            max_tokens=512,
            api_key="test-key",
        )

        assert result["tool_turns"] == 1
        assert "tool_proposals" not in result
        assert '"boiling_point"' in result["text"]

        assert len(requests) == 2
        follow_up_messages = requests[1]["messages"]
        user_messages = [message for message in follow_up_messages if message["role"] == "user"]
        tool_result_text = user_messages[-1]["content"][0]["content"]
        assert "373.15" in tool_result_text

    def test_call_anthropic_tool_loop_records_tool_proposals(self, monkeypatch):
        requests = []
        responses = iter([
            {
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "propose_tool",
                        "input": {
                            "tool_name": "steam_table_lookup",
                            "reason": "Need steam properties at saturation.",
                            "priority": "blocking",
                            "interface": {
                                "inputs": [{"name": "pressure", "type": "number", "unit": "kPa"}],
                                "outputs": [{"name": "enthalpy", "type": "number", "unit": "kJ/kg"}],
                            },
                        },
                    }
                ],
                "stop_reason": "tool_use",
                "model": "fake-sonnet",
            },
            {
                "usage": {"input_tokens": 40, "output_tokens": 30},
                "content": [
                    {
                        "type": "text",
                        "text": '{"reasoning":"Used fallback.","assumptions":[],"method":"manual",'
                                '"calculations":{},"outputs":{},"confidence":0.5,"skill_notes":""}',
                    }
                ],
                "stop_reason": "end_turn",
                "model": "fake-sonnet",
            },
        ])

        def fake_post_json(url, headers, body, timeout=120):
            requests.append(body)
            return next(responses)

        monkeypatch.setattr(providers, "_post_json", fake_post_json)

        result = providers.call_anthropic_tool_loop(
            system="system",
            user="user",
            model="fake-sonnet",
            temperature=0,
            max_tokens=512,
            api_key="test-key",
        )

        assert result["tool_turns"] == 1
        assert result["tool_proposals"][0]["tool_name"] == "steam_table_lookup"
        assert result["tool_proposals"][0]["priority"] == "blocking"
        assert result["tool_proposals"][0]["_turn"] == 1

        assert len(requests) == 2
        follow_up_messages = requests[1]["messages"]
        assert any(message["role"] == "assistant" for message in follow_up_messages)
        user_messages = [message for message in follow_up_messages if message["role"] == "user"]
        ack = user_messages[-1]["content"][0]["content"]
        assert "Proposal recorded" in ack
        assert "NOT available in the current session" in ack


class TestLayer3ProposalIntegration:

    def test_run_fixture_layer3_records_and_prints_tool_proposals(
        self, monkeypatch, tmp_path, minimal_fixture, capsys
    ):
        fixture_path = tmp_path / "fixture.json"
        fixture_path.write_text(json.dumps(minimal_fixture))

        results_dir = tmp_path / "results"
        traces_dir = tmp_path / "traces"
        artifacts_dir = tmp_path / "artifacts"
        archive_log = tmp_path / "archive.jsonl"
        results_dir.mkdir()
        monkeypatch.setattr(run_eval, "RESULTS_DIR", results_dir)
        monkeypatch.setattr(run_eval, "TRACES_DIR", traces_dir)
        monkeypatch.setattr(run_eval, "ARTIFACTS_DIR", artifacts_dir)
        monkeypatch.setattr(run_eval, "ARCHIVE_LOG", archive_log)
        monkeypatch.setattr(run_eval, "get_git_sha", lambda: "deadbee")
        monkeypatch.setattr(run_eval, "get_api_key", lambda provider_name: "test-key")

        raw_response = {
            "text": json.dumps(
                {
                    "reasoning": (
                        "Use Antoine equation for vapor pressure and convert units "
                        "between mmHg and kPa with ideal behavior assumptions."
                    ),
                    "assumptions": ["Ideal gas vapor phase"],
                    "method": "Antoine equation",
                    "calculations": {"P_mmHg": 760, "T_C": 100.0},
                    "outputs": {"boiling_point": {"value": 373.15, "unit": "K"}},
                    "confidence": 0.9,
                    "skill_notes": "",
                }
            ),
            "model": "fake-sonnet",
            "input_tokens": 123,
            "output_tokens": 45,
            "tool_turns": 1,
            "tool_proposals": [
                {
                    "tool_name": "steam_table_lookup",
                    "reason": "Need steam properties at saturation.",
                    "priority": "blocking",
                    "_turn": 1,
                }
            ],
        }
        monkeypatch.setattr(run_eval, "call_anthropic_tool_loop", lambda **kwargs: raw_response)

        result = run_eval.run_fixture(
            str(fixture_path),
            provider_name="anthropic",
            model="fake-sonnet",
            layer=3,
            use_judge=False,
        )

        output = capsys.readouterr().out
        assert "REASONING (ROUGH HEURISTIC)" in output
        assert "rough heuristic only" in output.lower()
        assert "TOOL PROPOSALS: 1" in output
        assert "steam_table_lookup" in output

        assert result["agent_meta"]["tool_turns"] == 1
        assert result["tool_proposals"][0]["tool_name"] == "steam_table_lookup"
        assert result["tool_proposals"][0]["priority"] == "blocking"
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["artifact_type"] == "tool"
        assert result["artifacts"][0]["status"] == "proposed"
        assert result["artifacts"][0]["source_run_id"] == result["run_id"]

        saved_results = list(results_dir.glob("test-fixture-01-L3-deadbee-*.json"))
        assert len(saved_results) == 1

        trace_path = traces_dir / f"{result['run_id']}.jsonl"
        assert trace_path.exists()
        events = [json.loads(line) for line in trace_path.read_text().splitlines()]
        assert "artifact_proposed" in [event["type"] for event in events]
        proposal_events = [event for event in events if event["type"] == "artifact_proposed"]
        assert proposal_events[0]["payload"]["artifact_type"] == "tool"
        assert proposal_events[0]["payload"]["artifact_id"] == result["artifacts"][0]["artifact_id"]
        assert proposal_events[0]["payload"]["proposal"]["tool_name"] == "steam_table_lookup"

        artifact_path = Path(result["artifacts"][0]["artifact_path"])
        assert artifact_path.exists()
        artifact_payload = json.loads(artifact_path.read_text())
        assert artifact_payload["artifact_id"] == result["artifacts"][0]["artifact_id"]
        assert artifact_payload["artifact_type"] == "tool"
        assert artifact_payload["status"] == "proposed"
        assert artifact_payload["source_run_id"] == result["run_id"]
        assert artifact_payload["proposal"]["tool_name"] == "steam_table_lookup"

        archive_records = [json.loads(line) for line in archive_log.read_text().splitlines()]
        assert [record["record_type"] for record in archive_records] == ["artifact", "run"]
        assert archive_records[0]["payload"]["artifact_id"] == result["artifacts"][0]["artifact_id"]
        assert archive_records[1]["record_id"] == result["run_id"]


class TestArtifactRegistry:

    def test_transition_artifact_status_updates_record_and_archive(self, monkeypatch, tmp_path):
        artifact_dir = tmp_path / "artifacts"
        archive_log = tmp_path / "archive.jsonl"
        monkeypatch.setattr(run_eval, "ARTIFACTS_DIR", artifact_dir)
        monkeypatch.setattr(run_eval, "ARCHIVE_LOG", archive_log)

        artifact = run_eval.record_artifact(
            run_id="run-123",
            fixture={"id": "fixture-1", "version": "1.0.0"},
            artifact_type="tool",
            proposal={"tool_name": "steam_table_lookup", "reason": "Need steam properties"},
            git_sha="deadbee",
        )

        updated = run_eval.transition_artifact_status(
            artifact["artifact_id"],
            "validated",
            reviewer="ted",
            notes="Passed initial review",
        )

        assert updated["status"] == "validated"
        assert updated["validation"]["status"] == "validated"
        assert updated["validation"]["tests_passed"] is True
        assert updated["validation"]["reviewed_by"] == "ted"
        assert updated["lifecycle"][-1]["from_status"] == "proposed"
        assert updated["lifecycle"][-1]["to_status"] == "validated"

        archive_records = [json.loads(line) for line in archive_log.read_text().splitlines()]
        assert [record["record_type"] for record in archive_records] == ["artifact", "artifact_transition"]
        assert archive_records[1]["payload"]["from_status"] == "proposed"
        assert archive_records[1]["payload"]["to_status"] == "validated"

    def test_invalid_artifact_transition_raises(self, monkeypatch, tmp_path):
        artifact_dir = tmp_path / "artifacts"
        archive_log = tmp_path / "archive.jsonl"
        monkeypatch.setattr(run_eval, "ARTIFACTS_DIR", artifact_dir)
        monkeypatch.setattr(run_eval, "ARCHIVE_LOG", archive_log)

        artifact = run_eval.record_artifact(
            run_id="run-123",
            fixture={"id": "fixture-1", "version": "1.0.0"},
            artifact_type="tool",
            proposal={"tool_name": "steam_table_lookup", "reason": "Need steam properties"},
            git_sha="deadbee",
        )

        try:
            run_eval.transition_artifact_status(artifact["artifact_id"], "promoted")
            assert False, "Expected invalid transition to raise"
        except ValueError as exc:
            assert "Invalid artifact transition" in str(exc)


class TestArtifactCli:

    def test_list_show_and_transition_artifact_commands(self, monkeypatch, tmp_path):
        artifact_dir = tmp_path / "artifacts"
        archive_log = tmp_path / "archive.jsonl"
        monkeypatch.setattr(run_eval, "ARTIFACTS_DIR", artifact_dir)
        monkeypatch.setattr(run_eval, "ARCHIVE_LOG", archive_log)

        artifact = run_eval.record_artifact(
            run_id="run-123",
            fixture={"id": "fixture-1", "version": "1.0.0"},
            artifact_type="tool",
            proposal={"tool_name": "steam_table_lookup", "reason": "Need steam properties"},
            git_sha="deadbee",
        )

        original_argv = sys.argv[:]
        try:
            sys.argv = ["run_eval.py", "--list-artifacts"]
            out = StringIO()
            with redirect_stdout(out):
                run_eval.main()
            listed = out.getvalue()
            assert artifact["artifact_id"] in listed
            assert "steam_table_lookup" in listed

            sys.argv = ["run_eval.py", "--show-artifact", "--artifact-id", artifact["artifact_id"]]
            out = StringIO()
            with redirect_stdout(out):
                run_eval.main()
            shown = json.loads(out.getvalue())
            assert shown["artifact_id"] == artifact["artifact_id"]

            sys.argv = [
                "run_eval.py",
                "--transition-artifact", "validated",
                "--artifact-id", artifact["artifact_id"],
                "--reviewer", "ted",
                "--notes", "cli validation",
            ]
            out = StringIO()
            with redirect_stdout(out):
                run_eval.main()
            transitioned = out.getvalue()
            assert "-> validated" in transitioned

            updated = run_eval.load_artifact(artifact["artifact_id"])
            assert updated["status"] == "validated"
            assert updated["validation"]["reviewed_by"] == "ted"
        finally:
            sys.argv = original_argv


class TestTraceCli:

    def test_trace_summary_command_prints_run_overview(self, monkeypatch, tmp_path):
        traces_dir = tmp_path / "traces"
        artifacts_dir = tmp_path / "artifacts"
        archive_log = tmp_path / "archive.jsonl"
        monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(run_eval, "TRACES_DIR", traces_dir)
        monkeypatch.setattr(run_eval, "ARTIFACTS_DIR", artifacts_dir)
        monkeypatch.setattr(run_eval, "ARCHIVE_LOG", archive_log)
        monkeypatch.setattr(run_eval, "get_git_sha", lambda: "deadbee")

        fixture_path = PROJECT_ROOT / "fixtures" / "flash-distillation-01.json"
        result = run_eval.run_fixture(str(fixture_path), use_mock=True, layer=1, use_judge=False)

        original_argv = sys.argv[:]
        try:
            sys.argv = [
                "run_eval.py",
                "--trace-summary",
                "--run-id", result["run_id"],
            ]
            out = StringIO()
            with redirect_stdout(out):
                run_eval.main()
            summary = out.getvalue()
            assert f"TRACE SUMMARY: {result['run_id']}" in summary
            assert "flash-distillation-01" in summary
            assert "scores_computed" in summary
            assert "run_completed" in summary
        finally:
            sys.argv = original_argv

    def test_trace_summary_can_filter_event_types(self, monkeypatch, tmp_path):
        traces_dir = tmp_path / "traces"
        artifacts_dir = tmp_path / "artifacts"
        archive_log = tmp_path / "archive.jsonl"
        monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(run_eval, "TRACES_DIR", traces_dir)
        monkeypatch.setattr(run_eval, "ARTIFACTS_DIR", artifacts_dir)
        monkeypatch.setattr(run_eval, "ARCHIVE_LOG", archive_log)
        monkeypatch.setattr(run_eval, "get_git_sha", lambda: "deadbee")

        fixture_path = PROJECT_ROOT / "fixtures" / "flash-distillation-01.json"
        result = run_eval.run_fixture(str(fixture_path), use_mock=True, layer=1, use_judge=False)

        original_argv = sys.argv[:]
        try:
            sys.argv = [
                "run_eval.py",
                "--trace-summary",
                "--run-id", result["run_id"],
                "--trace-event-type", "scores_computed",
            ]
            out = StringIO()
            with redirect_stdout(out):
                run_eval.main()
            summary = out.getvalue()
            assert "scores_computed" in summary
            assert "run_started" not in summary.split("  EVENTS", 1)[1]
        finally:
            sys.argv = original_argv
