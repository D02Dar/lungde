from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from threading import Lock, RLock
from typing import Any, Iterator
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisStore:
    def __init__(self, root: Path | None = None):
        configured = os.environ.get("WENT_DATA_DIR")
        self.root = Path(configured) if configured else (root or Path(__file__).resolve().parents[1] / "data")
        self.video_dir = self.root / "videos"
        self.evidence_dir = self.root / "evidence"
        self.root.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = self.root / "analyses.sqlite3"
        self._locks_guard = Lock()
        self._analysis_locks: dict[str, RLock] = {}
        self._initialise()

    @contextmanager
    def analysis_lock(self, analysis_id: str) -> Iterator[None]:
        with self._locks_guard:
            lock = self._analysis_locks.setdefault(analysis_id, RLock())
        with lock:
            yield

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    frontend_record_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    original_filename TEXT,
                    mime_type TEXT,
                    byte_size INTEGER NOT NULL DEFAULT 0,
                    declared_duration_ms REAL,
                    video_path TEXT NOT NULL,
                    sha256 TEXT,
                    capture_metadata_json TEXT NOT NULL,
                    manual_roi_json TEXT,
                    diagnostics_json TEXT,
                    result_json TEXT,
                    error_code TEXT,
                    error_message TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    key TEXT NOT NULL,
                    label TEXT NOT NULL,
                    elapsed_ms REAL NOT NULL,
                    image_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS evidence_analysis_idx ON evidence(analysis_id)")

    def allocate_video(self, suffix: str = ".webm") -> tuple[str, Path]:
        analysis_id = uuid4().hex
        safe_suffix = suffix if suffix.startswith(".") and len(suffix) <= 12 else ".webm"
        return analysis_id, self.video_dir / f"{analysis_id}{safe_suffix}"

    def allocate_evidence(self, analysis_id: str, key: str, suffix: str = ".webp") -> tuple[str, Path]:
        evidence_id = uuid4().hex
        safe_key = "".join(character for character in key if character.isalnum() or character in "-_")[:48] or "frame"
        directory = self.evidence_dir / analysis_id
        directory.mkdir(parents=True, exist_ok=True)
        return evidence_id, directory / f"{evidence_id}-{safe_key}{suffix}"

    def create(
        self,
        *,
        analysis_id: str,
        frontend_record_id: str | None,
        filename: str,
        mime_type: str,
        byte_size: int,
        declared_duration_ms: float | None,
        video_path: Path,
        capture_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        digest = hashlib.sha256(video_path.read_bytes()).hexdigest()
        relative_path = video_path.relative_to(self.root).as_posix()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analyses (
                    id, frontend_record_id, created_at, updated_at, status,
                    original_filename, mime_type, byte_size, declared_duration_ms,
                    video_path, sha256, capture_metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id, frontend_record_id, now, now, "uploaded",
                    filename, mime_type, byte_size, declared_duration_ms,
                    relative_path, digest, json.dumps(capture_metadata),
                ),
            )
        return self.get(analysis_id)

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        return self._row(row) if row else None

    def update(self, analysis_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "status", "manual_roi_json", "diagnostics_json", "result_json",
            "error_code", "error_message", "capture_metadata_json",
        }
        values = {key: value for key, value in fields.items() if key in allowed}
        if not values:
            return self.get(analysis_id)
        values["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE analyses SET {assignments} WHERE id = ?",
                (*values.values(), analysis_id),
            )
        return self.get(analysis_id)

    def add_evidence(self, analysis_id: str, metadata: dict[str, Any], image_path: Path) -> dict[str, Any]:
        relative_path = image_path.relative_to(self.root).as_posix()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence (id, analysis_id, created_at, key, label, elapsed_ms, image_path, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata["id"], analysis_id, utc_now(), metadata["key"], metadata["label"],
                    metadata["elapsed_ms"], relative_path, json.dumps(metadata),
                ),
            )
        return self.get_evidence(analysis_id, metadata["id"])

    def list_evidence(self, analysis_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM evidence WHERE analysis_id = ? ORDER BY elapsed_ms, created_at",
                (analysis_id,),
            ).fetchall()
        return [self._evidence_row(row) for row in rows]

    def get_evidence(self, analysis_id: str, evidence_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM evidence WHERE analysis_id = ? AND id = ?",
                (analysis_id, evidence_id),
            ).fetchone()
        return self._evidence_row(row) if row else None

    def clear_evidence(self, analysis_id: str) -> None:
        directory = self.evidence_dir / analysis_id
        with self._connect() as connection:
            connection.execute("DELETE FROM evidence WHERE analysis_id = ?", (analysis_id,))
        shutil.rmtree(directory, ignore_errors=True)

    def delete(self, analysis_id: str) -> bool:
        record = self.get(analysis_id)
        if not record:
            return False
        self.clear_evidence(analysis_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        try:
            self.video_path(record).unlink(missing_ok=True)
        except OSError:
            pass
        return True

    def video_path(self, record: dict[str, Any]) -> Path:
        return self.root / record["video_path"]

    def evidence_path(self, record: dict[str, Any]) -> Path:
        return self.root / record["image_path"]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for column in ("capture_metadata_json", "manual_roi_json", "diagnostics_json", "result_json"):
            value = result.pop(column, None)
            result[column.removesuffix("_json")] = json.loads(value) if value else None
        return result

    @staticmethod
    def _evidence_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        metadata = json.loads(result.pop("metadata_json"))
        return {**result, **metadata}


analysis_store = AnalysisStore()
