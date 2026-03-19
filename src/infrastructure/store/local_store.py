"""Local JSON-based simulation history store.

Persists simulation run metadata and summaries as individual JSON files
in a local directory. Designed for the Streamlit dashboard to support
run history browsing, comparison, and CSV export.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LocalSimulationStore:
    """Stores simulation runs as JSON files in a local directory."""

    def __init__(self, store_dir: str = ".simulation_history") -> None:
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run: dict[str, Any]) -> str:
        """Save run data and return the generated run_id (UUID).

        The saved JSON contains run_id, feature, created_at (ISO timestamp),
        config, result_summary, and distribution.
        """
        run_id = uuid.uuid4().hex
        created_at = datetime.now(tz=UTC).isoformat()

        record: dict[str, Any] = {
            "run_id": run_id,
            "feature": run.get("feature", "unknown"),
            "created_at": created_at,
            "config": run.get("config", {}),
            "result_summary": run.get("result_summary", {}),
            "distribution": run.get("distribution", {}),
        }

        file_path = self._store_dir / f"{run_id}.json"
        with open(file_path, "w") as f:
            json.dump(record, f, indent=2)

        logger.info("Saved simulation run %s to %s", run_id, file_path)
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Get run by ID. Raises FileNotFoundError if not found."""
        file_path = self._store_dir / f"{run_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"No simulation run found with id: {run_id}")

        with open(file_path) as f:
            data: dict[str, Any] = json.load(f)

        logger.debug("Retrieved simulation run %s", run_id)
        return data

    def list_runs(
        self,
        feature: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List runs sorted by created_at descending.

        Args:
            feature: Optional filter by feature name (e.g. "coin_flip").
            limit: Maximum number of runs to return.
        """
        runs: list[dict[str, Any]] = []

        for file_path in self._store_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    record: dict[str, Any] = json.load(f)
                if feature is not None and record.get("feature") != feature:
                    continue
                runs.append(record)
            except (json.JSONDecodeError, KeyError):
                logger.warning("Skipping corrupt file: %s", file_path)
                continue

        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)

        logger.debug("Listed %d runs (feature=%s, limit=%d)", len(runs), feature, limit)
        return runs[:limit]

    def delete_run(self, run_id: str) -> None:
        """Delete a run by ID. Raises FileNotFoundError if not found."""
        file_path = self._store_dir / f"{run_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"No simulation run found with id: {run_id}")

        file_path.unlink()
        logger.info("Deleted simulation run %s", run_id)
