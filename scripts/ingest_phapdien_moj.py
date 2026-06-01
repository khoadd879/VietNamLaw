#!/usr/bin/env python3
"""
Ingestion script for tmquan/phapdien-moj-gov-vn dataset.
Loads articles directly (already cleaned), splits if too large, and upserts to Qdrant Cloud.
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
    LEGAL_ARTICLE_CHAPTER_THRESHOLD,
    LEGAL_CHUNK_MAX_CHARS,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
)
from services.qdrant_service import (  # noqa: E402
    ensure_collection_exists,
    get_qdrant_client,
    ingest_articles,
    split_legal_chunks,
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


def build_chunk_records(row: dict, row_index: int) -> list[dict]:
    content_text = (row.get("content_text") or "").strip()
    if not content_text:
        return []

    # Skip cực lớn (>100K chars) - thường là bảng dữ liệu, không phù hợp embed
    if len(content_text) > 100000:
        return []

    article_anchor = row.get("article_anchor") or f"article_{row_index}"
    doc_id = str(article_anchor).lstrip("#") or f"article_{row_index}"

    if len(content_text) <= LEGAL_CHUNK_MAX_CHARS:
        chunks = [{
            "content_text": content_text,
            "chapter_label": row.get("chapter_title"),
            "article_label": row.get("article_title"),
            "chunk_level": "article",
        }]
    else:
        chunks = split_legal_chunks(
            content_text,
            max_chars=LEGAL_CHUNK_MAX_CHARS,
            article_threshold=LEGAL_ARTICLE_CHAPTER_THRESHOLD,
        )
        chunks = [c for c in chunks if str(c.get("content_text", "") or "").strip()]
        # Cap số chunk để tránh article quá lớn tạo ra hàng trăm chunk
        if len(chunks) > 30:
            chunks = chunks[:30]

    total_chunks = len(chunks)
    records = []
    for chunk_index, chunk in enumerate(chunks):
        records.append({
            "id": f"{doc_id}:{chunk_index}",
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "content_text": str(chunk.get("content_text", "") or ""),
            "chapter_label": chunk.get("chapter_label") or row.get("chapter_title"),
            "article_label": chunk.get("article_label") or row.get("article_title"),
            "chunk_level": chunk.get("chunk_level", "article"),
            "title": row.get("article_title", "") or "",
            "subject_title": row.get("subject_title", "") or "",
            "topic_title": row.get("topic_title", "") or "",
            "source_url": row.get("source_url", "") or "",
            "source_note": row.get("source_note_text", "") or "",
            "related_note": row.get("related_note_text", "") or "",
            "relationships": [],
        })
    return records


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
    print("phapdien-moj-gov-vn Ingestion Script")
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
        records = build_chunk_records(row, i)
        if not records:
            continue
        pending.extend(records)
        processed += 1

        should_flush = len(pending) >= batch_size
        reached_limit = args.limit is not None and processed >= args.limit
        at_end = i == end_index
        if not should_flush and not reached_limit and not at_end:
            continue

        if pending:
            print(f"\nUpserting {len(pending)} chunks after index {i}")
            ingest_articles(pending, batch_size=batch_size)
            last_id = pending[-1]["id"]
            save_checkpoint(i, last_id, checkpoint_path=checkpoint_path, worker_id=args.worker_id)
            print(f"  Checkpoint saved: index {i}, last chunk {last_id}")
            pending = []

        if reached_limit:
            break

    print("\n" + "=" * 60)
    print(f"Done! Articles processed: {processed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
