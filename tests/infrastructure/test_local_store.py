"""Tests for LocalSimulationStore — JSON-based simulation history persistence."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import polars as pl
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
        with pytest.raises(FileNotFoundError):
            store.get_run("nonexistent-id")


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
            store.update_run("nonexistent-id", {"name": "nope"})


class TestDeleteRun:
    """Tests for delete_run()."""

    def test_delete_run_removes_file(self, store: LocalSimulationStore) -> None:
        run_id = store.save_run(_make_run())
        store.delete_run(run_id)

        assert store.list_runs() == []

    def test_delete_nonexistent_run_raises(self, store: LocalSimulationStore) -> None:
        with pytest.raises(FileNotFoundError):
            store.delete_run("nonexistent-id")


# ---------------------------------------------------------------------------
# Parquet roundtrip tests (player_results persistence)
# ---------------------------------------------------------------------------


class TestPlayerResultsParquet:
    """Tests for save_run with player_results and load_player_results."""

    def test_save_and_load_player_results(
        self, store: LocalSimulationStore
    ) -> None:
        """Save player_results DataFrame, then load and verify schema/rows/values match."""
        player_results = pl.DataFrame(
            {
                "user_id": [1, 2, 3],
                "rolls_sink": [100, 200, 300],
                "avg_multiplier": [10, 20, 30],
                "about_to_churn": [False, True, False],
                "total_points": [50.5, 120.3, 200.0],
                "num_interactions": [10, 10, 10],
            }
        )
        run_data = _make_run()
        run_id = store.save_run(run_data, player_results=player_results)

        loaded = store.load_player_results(run_id)

        assert loaded is not None
        assert loaded.schema == player_results.schema
        assert loaded.height == player_results.height
        assert loaded["user_id"].to_list() == player_results["user_id"].to_list()
        assert loaded["total_points"].to_list() == pytest.approx(
            player_results["total_points"].to_list()
        )
        assert loaded["about_to_churn"].to_list() == player_results["about_to_churn"].to_list()

    def test_load_player_results_nonexistent(
        self, store: LocalSimulationStore
    ) -> None:
        """load_player_results returns None for an unknown run_id."""
        result = store.load_player_results("nonexistent-run-id")
        assert result is None

    def test_save_without_player_results_then_load(
        self, store: LocalSimulationStore
    ) -> None:
        """When saved without player_results, load_player_results returns None."""
        run_data = _make_run()
        run_id = store.save_run(run_data)

        result = store.load_player_results(run_id)
        assert result is None

    def test_save_with_player_results_sets_flag(
        self, store: LocalSimulationStore
    ) -> None:
        """Saving with player_results sets has_player_results=True in JSON."""
        player_results = pl.DataFrame(
            {
                "user_id": [1],
                "total_points": [42.0],
            }
        )
        run_data = _make_run()
        run_id = store.save_run(run_data, player_results=player_results)

        retrieved = store.get_run(run_id)
        assert retrieved.get("has_player_results") is True

    def test_save_without_player_results_no_flag(
        self, store: LocalSimulationStore
    ) -> None:
        """Saving without player_results does not set has_player_results."""
        run_data = _make_run()
        run_id = store.save_run(run_data)

        retrieved = store.get_run(run_id)
        assert "has_player_results" not in retrieved

    def test_delete_run_removes_parquet(
        self, store: LocalSimulationStore, tmp_path: Path
    ) -> None:
        """Deleting a run also removes its Parquet file."""
        player_results = pl.DataFrame({"user_id": [1], "total_points": [10.0]})
        run_data = _make_run()
        run_id = store.save_run(run_data, player_results=player_results)

        # Verify parquet exists
        assert store.load_player_results(run_id) is not None

        store.delete_run(run_id)

        # Parquet should be gone
        assert store.load_player_results(run_id) is None
