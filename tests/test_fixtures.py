"""
Fixture regression tests.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_eval import load_fixture


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestFixtures:

    def test_all_fixture_json_files_load(self):
        fixture_paths = sorted(
            path for path in FIXTURES_DIR.glob("*.json")
            if path.name != "fixture-schema.json"
        )

        loaded = [load_fixture(str(path)) for path in fixture_paths]

        assert len(loaded) >= 3
        assert all("id" in fixture for fixture in loaded)

    def test_capability_gap_fixture_set_present(self):
        fixture_ids = set()
        for path in FIXTURES_DIR.glob("*.json"):
            if path.name == "fixture-schema.json":
                continue
            with open(path) as f:
                fixture_ids.add(json.load(f)["id"])

        assert "steam-table-saturation-01" in fixture_ids
        assert "provided-antoine-ethanol-01" in fixture_ids
        assert "local-steam-table-interpolation-01" in fixture_ids
