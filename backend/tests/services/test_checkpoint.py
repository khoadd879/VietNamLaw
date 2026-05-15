"""Tests for checkpoint save/load logic used in ingestion script.

These tests verify the checkpoint logic that persists ingestion state.
The actual checkpoint functions mirror the logic in scripts/ingest_phapdien.py.
"""
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def get_checkpoint_path() -> Path:
    """Stub matching ingest script's get_checkpoint_path."""
    return Path(__file__).parent.parent.parent.parent / "data" / ".ingest_checkpoint.json"


def save_checkpoint(last_processed_index: int, last_processed_id: str) -> None:
    """Save checkpoint after each batch - mirrors ingest_phapdien.py logic."""
    checkpoint = {
        "last_processed_index": last_processed_index,
        "last_processed_id": last_processed_id,
        "timestamp": datetime.now().isoformat(),
    }
    path = get_checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def load_checkpoint() -> dict | None:
    """Load checkpoint if exists - mirrors ingest_phapdien.py logic."""
    path = get_checkpoint_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def test_checkpoint_save_load() -> None:
    """Write checkpoint -> read -> verify values match."""
    checkpoint_data = {
        "last_processed_index": 12500,
        "last_processed_id": "article-anchor-12345",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_path = Path(tmpdir) / ".ingest_checkpoint.json"

        with patch(__name__ + ".get_checkpoint_path", return_value=mock_path):
            save_checkpoint(
                last_processed_index=checkpoint_data["last_processed_index"],
                last_processed_id=checkpoint_data["last_processed_id"],
            )

            assert mock_path.exists(), "Checkpoint file should be created"

            loaded = load_checkpoint()
            assert loaded is not None, "Checkpoint should be loaded"
            assert loaded["last_processed_index"] == checkpoint_data["last_processed_index"]
            assert loaded["last_processed_id"] == checkpoint_data["last_processed_id"]
            assert "timestamp" in loaded, "Timestamp should be included"


def test_checkpoint_load_returns_none_when_missing() -> None:
    """Load checkpoint returns none when file does not exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_path = Path(tmpdir) / "nonexistent.json"

        with patch(__name__ + ".get_checkpoint_path", return_value=mock_path):
            result = load_checkpoint()
            assert result is None, "Should return None when checkpoint missing"


def test_checkpoint_overwrites_existing() -> None:
    """Save checkpoint overwrites previous values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_path = Path(tmpdir) / ".ingest_checkpoint.json"

        with patch(__name__ + ".get_checkpoint_path", return_value=mock_path):
            save_checkpoint(last_processed_index=100, last_processed_id="first-id")
            first = load_checkpoint()
            assert first["last_processed_index"] == 100

            save_checkpoint(last_processed_index=200, last_processed_id="second-id")
            second = load_checkpoint()
            assert second["last_processed_index"] == 200
            assert second["last_processed_id"] == "second-id"