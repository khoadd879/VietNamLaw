#!/usr/bin/env python3
"""
Ingestion script for tmquan/phapdien-moj-gov-vn dataset.
Loads articles directly (already cleaned, one article per row) and upserts
each row to Qdrant Cloud as a single point — no chunking.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from core.config import (  # noqa: E402
    INGEST_BATCH_SIZE,
    PHAPDIEN_MAX_CONTENT_CHARS,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
)
from services.qdrant_service import (  # noqa: E402
    ensure_collection_exists,
    get_qdrant_client,
    ingest_articles,
)


DATASET_NAME = "tmquan/phapdien-moj-gov-vn"
DATASET_CONFIG = "articles"
DATASET_SPLIT = "train"


def get_checkpoint_path(worker_id: str | None = None) -> Path:
    base = Path(__file__).parent.parent / "data"
    if worker_id is not None:
        return base / f".ingest_phapdien_moj_w{worker_id}.json"
    return base / ".ingest_phapdien_moj.json"


def load_checkpoint(checkpoint_path: Path | None = None, worker_id: str | None = None) -> dict | None:
    path = checkpoint_path or get_checkpoint_path(worker_id=worker_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_checkpoint(last_processed_index: int, last_processed_id: str, checkpoint_path: Path | None = None, worker_id: str | None = None) -> None:
    checkpoint: dict[str, object] = {
        "last_processed_index": last_processed_index,
        "last_processed_id": last_processed_id,
        "timestamp": datetime.now().isoformat(),
    }
    if worker_id is not None:
        checkpoint["worker_id"] = worker_id
    path = checkpoint_path or get_checkpoint_path(worker_id=worker_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def build_point_record(row: dict, row_index: int) -> dict | None:
    """Build a single Qdrant-ready record from one phapdien-moj dataset row.

    Returns None when the row should be skipped (empty content, oversized
    content beyond embedder capacity, or missing anchor).
    """
    content_text = (row.get("content_text") or "").strip()
    if not content_text:
        return None

    if len(content_text) > PHAPDIEN_MAX_CONTENT_CHARS:
        # bge-m3 max ≈ 8K tokens (~20K Vietnamese chars); the top 0.5% of
        # rows in this dataset are clearly corrupted/legal-compilation dumps
        # (8MB, 530K, 447K chars) and would exceed the embedder's window.
        print(
            f"  [skip] row {row_index} anchor={row.get('article_anchor')!r} "
            f"content too long ({len(content_text)} chars > {PHAPDIEN_MAX_CONTENT_CHARS})"
        )
        return None

    article_anchor = row.get("article_anchor")
    if not article_anchor:
        print(f"  [skip] row {row_index} missing article_anchor")
        return None

    return {
        "id": str(article_anchor).lstrip("#"),
        "article_anchor": article_anchor,
        "article_title": row.get("article_title", "") or "",
        "content_text": content_text,
        "content_char_len": int(row.get("content_char_len") or len(content_text)),
        "content_word_count": int(row.get("content_word_count") or 0),
        "chapter_title": row.get("chapter_title", "") or "",
        "subject_id": row.get("subject_id", "") or "",
        "subject_number": int(row.get("subject_number") or 0),
        "subject_title": row.get("subject_title", "") or "",
        "topic_id": row.get("topic_id", "") or "",
        "topic_number": int(row.get("topic_number") or 0),
        "topic_title": row.get("topic_title", "") or "",
        "source_note_text": row.get("source_note_text", "") or "",
        "source_links": list(row.get("source_links") or []),
        "related_note_text": row.get("related_note_text", "") or "",
        "source_url": row.get("source_url", "") or "",
        "scraped_at": row.get("scraped_at", "") or "",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest tmquan/phapdien-moj-gov-vn into Qdrant")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reset-checkpoint", action="store_true")
    parser.add_argument("--start-index", type=int, default=None, dest="start_index")
    parser.add_argument("--end-index", type=int, default=None, dest="end_index")
    parser.add_argument("--checkpoint-path", type=str, default=None, dest="checkpoint_path")
    parser.add_argument("--worker-id", type=str, default=None, dest="worker_id")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print("=" * 60)
    print("phapdien-moj-gov-vn Ingestion Script (whole-article passthrough)")
    print("=" * 60)

    if not QDRANT_API_KEY:
        print("ERROR: QDRANT_API_KEY not set")
        sys.exit(1)

    checkpoint_path = Path(args.checkpoint_path) if args.checkpoint_path else None

    checkpoint = (
        None
        if args.reset_checkpoint or args.start_index is not None
        else load_checkpoint(checkpoint_path, worker_id=args.worker_id)
    )
    start_index = 0
    if checkpoint:
        start_index = checkpoint["last_processed_index"] + 1
        print(f"Resuming from checkpoint: index {start_index}")
        print(f"Last processed ID: {checkpoint['last_processed_id']}")
        print(f"Checkpoint time: {checkpoint['timestamp']}")
    elif args.start_index is not None:
        start_index = args.start_index
        print(f"Starting at --start-index: {start_index}")

    print(f"\nLoading dataset {DATASET_NAME} ({DATASET_CONFIG})...")
    dataset = load_dataset(DATASET_NAME, DATASET_CONFIG, split=DATASET_SPLIT)
    total = len(dataset)
    end_index = args.end_index if args.end_index is not None else total - 1

    if end_index < start_index:
        print(f"Range [{start_index}, {end_index}] empty — nothing to process.")
        return

    end_index = min(end_index, total - 1)
    print(f"Total articles: {total}")
    print(f"Processing range: [{start_index}, {end_index}]")

    print(f"\nEnsuring Qdrant collection '{QDRANT_COLLECTION_NAME}' exists...")
    client = get_qdrant_client()
    ensure_collection_exists(client)

    batch_size = INGEST_BATCH_SIZE
    pending: list[dict] = []
    processed = 0

    for i in range(start_index, end_index + 1):
        row = dataset[i]
        record = build_point_record(row, i)
        if record is None:
            continue
        pending.append(record)
        processed += 1

        should_flush = len(pending) >= batch_size
        reached_limit = args.limit is not None and processed >= args.limit
        at_end = i == end_index
        if not should_flush and not reached_limit and not at_end:
            continue

        if pending:
            print(f"\nUpserting {len(pending)} points after index {i}")
            ingest_articles(pending, batch_size=batch_size)
            last_id = pending[-1]["id"]
            save_checkpoint(i, last_id, checkpoint_path=checkpoint_path, worker_id=args.worker_id)
            print(f"  Checkpoint saved: index {i}, last point {last_id}")
            pending = []

        if reached_limit:
            break

    print("\n" + "=" * 60)
    print(f"Done! Articles processed: {processed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
