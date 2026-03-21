"""Local JSON-based simulation history store.

Persists simulation run metadata and summaries as individual JSON files
in a local directory. Optionally stores the full per-player DataFrame
as Parquet for reconstructing detailed results on load.

Uses a lightweight ``_index.json`` to cache run metadata (run_id,
created_at, feature) so that ``list_runs`` can sort and filter without
opening every run file.  The index is rebuilt automatically from disk
when it is missing or corrupt.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

_INDEX_FILENAME = "_index.json"


class LocalSimulationStore:
    """Stores simulation runs as JSON files in a local directory."""

    def __init__(self, store_dir: str | None = None) -> None:
        if store_dir is None:
            store_dir = os.environ.get("SIMULATION_STORE_DIR", ".simulation_history")
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._store_dir / _INDEX_FILENAME

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _load_index(self) -> dict[str, dict[str, str]]:
        """Load the index from disk, rebuilding if missing or corrupt.

        Returns a dict mapping run_id -> {"created_at": ..., "feature": ...}.
        """
        if self._index_path.exists():
            try:
                with open(self._index_path) as f:
                    index: dict[str, dict[str, str]] = json.load(f)
                return index
            except (json.JSONDecodeError, TypeError):
                logger.warning("Corrupt index file — rebuilding from disk")

        return self._rebuild_index()

    def _save_index(self, index: dict[str, dict[str, str]]) -> None:
        """Persist the index to disk."""
        with open(self._index_path, "w") as f:
            json.dump(index, f, indent=2)

    def _rebuild_index(self) -> dict[str, dict[str, str]]:
        """Scan all JSON run files and rebuild the index from scratch."""
        index: dict[str, dict[str, str]] = {}
        for file_path in self._store_dir.glob("*.json"):
            if file_path.name == _INDEX_FILENAME:
                continue
            try:
                with open(file_path) as f:
                    record: dict[str, Any] = json.load(f)
                run_id = record.get("run_id", file_path.stem)
                index[run_id] = {
                    "created_at": record.get("created_at", ""),
                    "feature": record.get("feature", "unknown"),
                }
            except (json.JSONDecodeError, KeyError):
                logger.warning("Skipping corrupt file during index rebuild: %s", file_path)
        self._save_index(index)
        logger.info("Rebuilt index with %d entries", len(index))
        return index

    def _add_to_index(
        self,
        run_id: str,
        created_at: str,
        feature: str,
    ) -> None:
        """Add a single entry to the index (read-modify-write)."""
        index = self._load_index()
        index[run_id] = {"created_at": created_at, "feature": feature}
        self._save_index(index)

    def _remove_from_index(self, run_id: str) -> None:
        """Remove a single entry from the index."""
        index = self._load_index()
        index.pop(run_id, None)
        self._save_index(index)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_run(
        self,
        run: dict[str, Any],
        player_results: pl.DataFrame | None = None,
    ) -> str:
        """Save run data and return the generated run_id (UUID).

        The saved JSON contains run_id, feature, created_at (ISO timestamp),
        config, result_summary, and distribution.  When *player_results* is
        provided, the full DataFrame is stored as a Parquet file alongside
        the JSON so that loaded runs can reconstruct all three result tabs.
        """
        run_id = uuid.uuid4().hex
        created_at = datetime.now(tz=UTC).isoformat()
        feature = run.get("feature", "unknown")

        record: dict[str, Any] = {
            "run_id": run_id,
            "name": run.get("name", ""),
            "feature": feature,
            "created_at": created_at,
            "config": run.get("config", {}),
            "result_summary": run.get("result_summary", {}),
            "distribution": run.get("distribution", {}),
        }

        # Save optional full player results as Parquet
        if player_results is not None:
            parquet_path = self._store_dir / f"{run_id}.parquet"
            player_results.write_parquet(parquet_path)
            record["has_player_results"] = True

        file_path = self._store_dir / f"{run_id}.json"
        with open(file_path, "w") as f:
            json.dump(record, f, indent=2)

        # Update the index
        self._add_to_index(run_id, created_at, feature)

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

        Uses the cached index for sorting and filtering so that only the
        top *limit* run files need to be read from disk (instead of all).

        Args:
            feature: Optional filter by feature name (e.g. "coin_flip").
            limit: Maximum number of runs to return.
        """
        index = self._load_index()

        # Filter by feature if requested
        if feature is not None:
            entries = [
                (rid, meta)
                for rid, meta in index.items()
                if meta.get("feature") == feature
            ]
        else:
            entries = list(index.items())

        # Sort by created_at descending
        entries.sort(key=lambda e: e[1].get("created_at", ""), reverse=True)

        # Only read the top N files from disk
        runs: list[dict[str, Any]] = []
        for rid, _meta in entries[:limit]:
            file_path = self._store_dir / f"{rid}.json"
            try:
                with open(file_path) as f:
                    record: dict[str, Any] = json.load(f)
                runs.append(record)
            except (FileNotFoundError, json.JSONDecodeError):
                logger.warning("Index references missing/corrupt file for run %s — skipping", rid)
                continue

        logger.debug("Listed %d runs (feature=%s, limit=%d)", len(runs), feature, limit)
        return runs

    def update_run(self, run_id: str, updates: dict[str, Any]) -> None:
        """Update fields on an existing run. Raises FileNotFoundError if not found."""
        file_path = self._store_dir / f"{run_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"No simulation run found with id: {run_id}")

        with open(file_path) as f:
            record: dict[str, Any] = json.load(f)

        record.update(updates)

        with open(file_path, "w") as f:
            json.dump(record, f, indent=2)

        # If feature or created_at changed, update the index too
        if "feature" in updates or "created_at" in updates:
            index = self._load_index()
            if run_id in index:
                if "feature" in updates:
                    index[run_id]["feature"] = updates["feature"]
                if "created_at" in updates:
                    index[run_id]["created_at"] = updates["created_at"]
                self._save_index(index)

        logger.info("Updated simulation run %s: %s", run_id, list(updates.keys()))

    def load_player_results(self, run_id: str) -> pl.DataFrame | None:
        """Load the full player results DataFrame for a run, if saved.

        Returns None if no Parquet file exists for this run.
        """
        parquet_path = self._store_dir / f"{run_id}.parquet"
        if not parquet_path.exists():
            return None
        return pl.read_parquet(parquet_path)

    def delete_run(self, run_id: str) -> None:
        """Delete a run by ID. Raises FileNotFoundError if not found."""
        file_path = self._store_dir / f"{run_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"No simulation run found with id: {run_id}")

        file_path.unlink()

        # Also remove the parquet file if it exists
        parquet_path = self._store_dir / f"{run_id}.parquet"
        if parquet_path.exists():
            parquet_path.unlink()

        # Remove from index
        self._remove_from_index(run_id)

        logger.info("Deleted simulation run %s", run_id)
