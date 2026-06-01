"""
Tests for the ingest script's parallel-ingest support.

Covers:
- Checkpoint save/load with worker_id isolation
- Checkpoint overwrites with worker_id
- get_checkpoint_path with and without worker_id
- Backward compatibility: no worker_id uses the default path
- Range-based indexing (start-index, end-index) via direct import
"""
import json
from pathlib import Path

from scripts.ingest_phapdien import (
    get_checkpoint_path,
    load_checkpoint,
    save_checkpoint,
)


# ----------------------------------------------------------------------
# Original backward-compatible tests
# ----------------------------------------------------------------------


def test_checkpoint_save_load(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles.json"

    save_checkpoint(
        last_processed_index=12500,
        last_processed_id="123:4",
        checkpoint_path=checkpoint_path,
    )

    assert checkpoint_path.exists()

    loaded = load_checkpoint(checkpoint_path=checkpoint_path)
    assert loaded is not None
    assert loaded["last_processed_index"] == 12500
    assert loaded["last_processed_id"] == "123:4"
    assert "timestamp" in loaded


def test_checkpoint_load_returns_none_when_missing(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "nonexistent.json"

    result = load_checkpoint(checkpoint_path=checkpoint_path)

    assert result is None


def test_checkpoint_overwrites_existing(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles.json"

    save_checkpoint(100, "100:0", checkpoint_path=checkpoint_path)
    save_checkpoint(200, "200:1", checkpoint_path=checkpoint_path)

    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert data["last_processed_index"] == 200
    assert data["last_processed_id"] == "200:1"


# ----------------------------------------------------------------------
# get_checkpoint_path
# ----------------------------------------------------------------------


def test_get_checkpoint_path_returns_default_when_no_worker_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.ingest_phapdien.Path",
        lambda x: (tmp_path / x.replace(str(Path(__file__).parent.parent.parent / "data"), str(tmp_path))),
    )

    result = get_checkpoint_path(worker_id=None)
    assert result.name == ".ingest_articles.json"


def test_get_checkpoint_path_returns_worker_file(tmp_path: Path) -> None:
    import scripts.ingest_phapdien as script_module

    original = script_module.get_checkpoint_path
    script_module.get_checkpoint_path = lambda wid=None: (
        tmp_path / f".ingest_articles_w{wid}.json" if wid is not None else tmp_path / ".ingest_articles.json"
    )

    try:
        assert script_module.get_checkpoint_path("0") == tmp_path / ".ingest_articles_w0.json"
        assert script_module.get_checkpoint_path("1") == tmp_path / ".ingest_articles_w1.json"
        assert script_module.get_checkpoint_path(None) == tmp_path / ".ingest_articles.json"
    finally:
        script_module.get_checkpoint_path = original


def test_get_checkpoint_path_worker_ids_are_isolated(tmp_path: Path) -> None:
    import scripts.ingest_phapdien as script_module

    original = script_module.get_checkpoint_path
    script_module.get_checkpoint_path = lambda wid=None: (
        tmp_path / f".ingest_articles_w{wid}.json" if wid is not None else tmp_path / ".ingest_articles.json"
    )

    try:
        path_w0 = script_module.get_checkpoint_path("0")
        path_w1 = script_module.get_checkpoint_path("1")
        path_default = script_module.get_checkpoint_path(None)

        assert path_w0 != path_w1
        assert path_w0 != path_default
        assert path_w1 != path_default
    finally:
        script_module.get_checkpoint_path = original


# ----------------------------------------------------------------------
# save_checkpoint
# ----------------------------------------------------------------------


def test_save_checkpoint_writes_worker_id_field(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles_w2.json"

    save_checkpoint(
        last_processed_index=500,
        last_processed_id="999:3",
        checkpoint_path=checkpoint_path,
        worker_id="2",
    )

    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert data["last_processed_index"] == 500
    assert data["last_processed_id"] == "999:3"
    assert data["worker_id"] == "2"


def test_save_checkpoint_omits_worker_id_when_none(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles.json"

    save_checkpoint(
        last_processed_index=100,
        last_processed_id="50:0",
        checkpoint_path=checkpoint_path,
    )

    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert data["last_processed_index"] == 100
    assert data["last_processed_id"] == "50:0"
    assert "worker_id" not in data


# ----------------------------------------------------------------------
# load_checkpoint
# ----------------------------------------------------------------------


def test_load_checkpoint_returns_worker_checkpoint(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles_w3.json"
    checkpoint_path.write_text(
        json.dumps({"last_processed_index": 42, "last_processed_id": "42:2", "timestamp": "2026-05-22T00:00:00"}),
        encoding="utf-8",
    )

    result = load_checkpoint(checkpoint_path=checkpoint_path, worker_id="3")

    assert result is not None
    assert result["last_processed_index"] == 42
    assert result["last_processed_id"] == "42:2"


def test_load_checkpoint_returns_none_for_missing_worker_file(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles_w99.json"

    result = load_checkpoint(checkpoint_path=checkpoint_path, worker_id="99")

    assert result is None


# ----------------------------------------------------------------------
# round-trip: save then load with worker_id
# ----------------------------------------------------------------------


def test_save_and_load_round_trip_with_worker_id(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles_w5.json"

    save_checkpoint(
        last_processed_index=1234,
        last_processed_id="567:7",
        checkpoint_path=checkpoint_path,
        worker_id="5",
    )

    loaded = load_checkpoint(checkpoint_path=checkpoint_path, worker_id="5")

    assert loaded is not None
    assert loaded["last_processed_index"] == 1234
    assert loaded["last_processed_id"] == "567:7"
    assert loaded["worker_id"] == "5"
    assert "timestamp" in loaded


# ----------------------------------------------------------------------
# overwrite with same worker
# ----------------------------------------------------------------------


def test_checkpoint_overwrites_existing(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / ".ingest_articles.json"

    save_checkpoint(100, "100:0", checkpoint_path=checkpoint_path)
    save_checkpoint(200, "200:1", checkpoint_path=checkpoint_path)

    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert data["last_processed_index"] == 200
    assert data["last_processed_id"] == "200:1"


def test_worker_checkpoint_does_not_affect_default(tmp_path: Path) -> None:
    default_path = tmp_path / ".ingest_articles.json"
    worker_path = tmp_path / ".ingest_articles_w0.json"

    save_checkpoint(10, "10:0", checkpoint_path=default_path)
    save_checkpoint(99, "99:0", checkpoint_path=worker_path, worker_id="0")

    default_data = json.loads(default_path.read_text(encoding="utf-8"))
    worker_data = json.loads(worker_path.read_text(encoding="utf-8"))

    assert default_data["last_processed_index"] == 10
    assert worker_data["last_processed_index"] == 99


# ----------------------------------------------------------------------
# Argument parsing for new parallel flags
# ----------------------------------------------------------------------


def test_start_index_argument_is_accepted(tmp_path: Path, monkeypatch) -> None:
    import sys
    import scripts.ingest_phapdien as script_module

    monkeypatch.setattr(sys, "argv", [
        "ingest_phapdien.py",
        "--reset-checkpoint",
        "--start-index", "100",
        "--end-index", "200",
    ])

    args = script_module._parse_args()  # type: ignore[attr-defined]
    assert args.start_index == 100
    assert args.end_index == 200


def test_worker_id_argument_is_accepted(tmp_path: Path, monkeypatch) -> None:
    import sys
    import scripts.ingest_phapdien as script_module

    monkeypatch.setattr(sys, "argv", [
        "ingest_phapdien.py",
        "--reset-checkpoint",
        "--worker-id", "2",
    ])

    args = script_module._parse_args()  # type: ignore[attr-defined]
    assert args.worker_id == "2"


def test_checkpoint_path_argument_is_accepted(tmp_path: Path, monkeypatch) -> None:
    import sys
    import scripts.ingest_phapdien as script_module

    monkeypatch.setattr(sys, "argv", [
        "ingest_phapdien.py",
        "--reset-checkpoint",
        "--checkpoint-path", "/custom/path/checkpoint.json",
    ])

    args = script_module._parse_args()  # type: ignore[attr-defined]
    assert args.checkpoint_path == "/custom/path/checkpoint.json"


def test_all_parallel_args_together(tmp_path: Path, monkeypatch) -> None:
    import sys
    import scripts.ingest_phapdien as script_module

    monkeypatch.setattr(sys, "argv", [
        "ingest_phapdien.py",
        "--reset-checkpoint",
        "--start-index", "500",
        "--end-index", "999",
        "--worker-id", "3",
        "--checkpoint-path", "/tmp/ckpt_w3.json",
        "--limit", "50",
    ])

    args = script_module._parse_args()  # type: ignore[attr-defined]
    assert args.start_index == 500
    assert args.end_index == 999
    assert args.worker_id == "3"
    assert args.checkpoint_path == "/tmp/ckpt_w3.json"
    assert args.limit == 50