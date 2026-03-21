"""Tests for LocalSimulationStore — JSON-based simulation history persistence."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from src.infrastructure.store.local_store import LocalSimulationStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> LocalSimulationStore:
    """Create a LocalSimulationStore backed by a temporary directory."""
    return LocalSimulationStore(store_dir=str(tmp_path / "history"))


def _make_run(
    feature: str = "coin_flip",
    total_points: float = 1000.0,
) -> dict[str, Any]:
    """Build a minimal run payload for testing."""
    return {
        "feature": feature,
        "config": {"max_successes": 5, "probabilities": [0.6, 0.5, 0.4, 0.3, 0.2]},
        "result_summary": {"total_points": total_points, "total_interactions": 500},
        "distribution": {"0": 200, "1": 150, "2": 100, "3": 30, "4": 15, "5": 5},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSaveRun:
    """Tests for save_run()."""

    def test_save_run_creates_json_file_and_returns_run_id(
        self, store: LocalSimulationStore, tmp_path: Path
    ) -> None:
        run_data = _make_run()
        run_id = store.save_run(run_data)

        assert isinstance(run_id, str)
        assert len(run_id) > 0

        # Verify a JSON file was created in the store directory
        store_dir = tmp_path / "history"
        json_files = list(store_dir.glob("*.json"))
        assert len(json_files) == 1

        # Verify the file contains valid JSON with expected fields
        with open(json_files[0]) as f:
            saved = json.load(f)
        assert saved["run_id"] == run_id
        assert saved["feature"] == "coin_flip"
        assert "created_at" in saved
        assert saved["config"] == run_data["config"]
        assert saved["result_summary"] == run_data["result_summary"]
        assert saved["distribution"] == run_data["distribution"]

    def test_save_multiple_runs_creates_multiple_files(
        self, store: LocalSimulationStore, tmp_path: Path
    ) -> None:
        store.save_run(_make_run(total_points=100.0))
        store.save_run(_make_run(total_points=200.0))
        store.save_run(_make_run(total_points=300.0))

        store_dir = tmp_path / "history"
        json_files = list(store_dir.glob("*.json"))
        assert len(json_files) == 3


class TestGetRun:
    """Tests for get_run()."""

    def test_get_run_retrieves_saved_run(self, store: LocalSimulationStore) -> None:
        run_data = _make_run(total_points=42.0)
        run_id = store.save_run(run_data)

        retrieved = store.get_run(run_id)

        assert retrieved["run_id"] == run_id
        assert retrieved["result_summary"]["total_points"] == 42.0
        assert retrieved["feature"] == "coin_flip"

    def test_get_run_raises_for_unknown_id(self, store: LocalSimulationStore) -> None:
        # Use a valid hex format that doesn't correspond to an existing run
        with pytest.raises(FileNotFoundError):
            store.get_run("a" * 32)


class TestListRuns:
    """Tests for list_runs()."""

    def test_list_runs_returns_sorted_by_created_at_descending(
        self, store: LocalSimulationStore
    ) -> None:
        store.save_run(_make_run(total_points=1.0))
        time.sleep(0.01)  # Ensure distinct timestamps
        store.save_run(_make_run(total_points=2.0))
        time.sleep(0.01)
        store.save_run(_make_run(total_points=3.0))

        runs = store.list_runs()

        assert len(runs) == 3
        # Most recent first
        assert runs[0]["result_summary"]["total_points"] == 3.0
        assert runs[1]["result_summary"]["total_points"] == 2.0
        assert runs[2]["result_summary"]["total_points"] == 1.0

    def test_list_runs_with_feature_filter(self, store: LocalSimulationStore) -> None:
        store.save_run(_make_run(feature="coin_flip"))
        store.save_run(_make_run(feature="loot_table"))
        store.save_run(_make_run(feature="coin_flip"))

        coin_runs = store.list_runs(feature="coin_flip")
        assert len(coin_runs) == 2
        assert all(r["feature"] == "coin_flip" for r in coin_runs)

        loot_runs = store.list_runs(feature="loot_table")
        assert len(loot_runs) == 1
        assert loot_runs[0]["feature"] == "loot_table"

    def test_list_runs_respects_limit(self, store: LocalSimulationStore) -> None:
        for i in range(5):
            store.save_run(_make_run(total_points=float(i)))

        runs = store.list_runs(limit=3)
        assert len(runs) == 3

    def test_empty_store_returns_empty_list(self, store: LocalSimulationStore) -> None:
        runs = store.list_runs()
        assert runs == []


class TestUpdateRun:
    """Tests for update_run()."""

    def test_update_run_modifies_field_on_disk(self, store: LocalSimulationStore) -> None:
        run_id = store.save_run(_make_run(total_points=100.0))
        store.update_run(run_id, {"name": "updated_name"})

        retrieved = store.get_run(run_id)
        assert retrieved["name"] == "updated_name"

    def test_update_run_preserves_other_fields(self, store: LocalSimulationStore) -> None:
        run_id = store.save_run(_make_run(feature="coin_flip", total_points=42.0))
        store.update_run(run_id, {"name": "new_name"})

        retrieved = store.get_run(run_id)
        assert retrieved["feature"] == "coin_flip"
        assert retrieved["result_summary"]["total_points"] == 42.0
        assert retrieved["config"]["max_successes"] == 5
        assert "created_at" in retrieved

    def test_update_run_nonexistent_raises(self, store: LocalSimulationStore) -> None:
        with pytest.raises(FileNotFoundError, match="No simulation run found"):
            store.update_run("a" * 32, {"name": "nope"})


class TestDeleteRun:
    """Tests for delete_run()."""

    def test_delete_run_removes_file(self, store: LocalSimulationStore) -> None:
        run_id = store.save_run(_make_run())
        store.delete_run(run_id)

        assert store.list_runs() == []

    def test_delete_nonexistent_run_raises(self, store: LocalSimulationStore) -> None:
        with pytest.raises(FileNotFoundError):
            store.delete_run("a" * 32)


class TestRunIdValidation:
    """Tests for run_id format validation — prevents path traversal attacks."""

    @pytest.mark.parametrize(
        "bad_run_id",
        [
            "../etc/passwd",
            "../../secrets",
            "nonexistent-id",
            "",
            "AABBCCDD11223344AABBCCDD11223344",  # uppercase hex
            "abc",  # too short
            "a" * 33,  # too long
            "a" * 31,  # one char short
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",  # non-hex chars
            "hello world 1234567890123456",  # spaces
            "../../../../../../tmp/evil",  # deep traversal
            "valid000000000000000000000000.json",  # with extension
            "a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p",  # slashes
        ],
    )
    def test_invalid_run_id_rejected_by_get_run(
        self, store: LocalSimulationStore, bad_run_id: str
    ) -> None:
        with pytest.raises(ValueError, match="Invalid run_id format"):
            store.get_run(bad_run_id)

    @pytest.mark.parametrize(
        "bad_run_id",
        [
            "../etc/passwd",
            "../../secrets",
            "nonexistent-id",
        ],
    )
    def test_invalid_run_id_rejected_by_update_run(
        self, store: LocalSimulationStore, bad_run_id: str
    ) -> None:
        with pytest.raises(ValueError, match="Invalid run_id format"):
            store.update_run(bad_run_id, {"name": "nope"})

    @pytest.mark.parametrize(
        "bad_run_id",
        [
            "../etc/passwd",
            "../../secrets",
            "nonexistent-id",
        ],
    )
    def test_invalid_run_id_rejected_by_load_player_results(
        self, store: LocalSimulationStore, bad_run_id: str
    ) -> None:
        with pytest.raises(ValueError, match="Invalid run_id format"):
            store.load_player_results(bad_run_id)

    @pytest.mark.parametrize(
        "bad_run_id",
        [
            "../etc/passwd",
            "../../secrets",
            "nonexistent-id",
        ],
    )
    def test_invalid_run_id_rejected_by_delete_run(
        self, store: LocalSimulationStore, bad_run_id: str
    ) -> None:
        with pytest.raises(ValueError, match="Invalid run_id format"):
            store.delete_run(bad_run_id)

    def test_valid_run_id_accepted(self, store: LocalSimulationStore) -> None:
        """A valid 32-char lowercase hex string should pass validation."""
        run_id = store.save_run(_make_run())
        # Should not raise — the run_id generated by save_run is valid
        retrieved = store.get_run(run_id)
        assert retrieved["run_id"] == run_id
