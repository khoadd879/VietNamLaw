#!/usr/bin/env python3
"""
Ingestion script for Vietnamese legal documents dataset.
Loads metadata via Hugging Face datasets, reads large HTML content via parquet,
chunks cleaned text, and upserts to Qdrant Cloud.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
from datasets import load_dataset
from huggingface_hub import hf_hub_download

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from core.config import (  # noqa: E402
    INGEST_BATCH_SIZE,
    LEGAL_ARTICLE_CHAPTER_THRESHOLD,
    LEGAL_CHUNK_MAX_CHARS,
    LEGAL_DATASET_CONTENT_CONFIG,
    LEGAL_DATASET_METADATA_CONFIG,
    LEGAL_DATASET_NAME,
    LEGAL_DATASET_RELATIONSHIPS_CONFIG,
    LEGAL_DATASET_SPLIT,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
)
from services.qdrant_service import (  # noqa: E402
    build_vbpl_source_url,
    clean_html_text,
    ensure_collection_exists,
    get_qdrant_client,
    ingest_articles,
    split_legal_chunks,
)


def get_checkpoint_path(worker_id: str | None = None) -> Path:
    base = Path(__file__).parent.parent / "data"
    if worker_id is not None:
        return base / f".ingest_articles_w{worker_id}.json"
    return base / ".ingest_articles.json"


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


def get_parquet_path(filename: str) -> str:
    return hf_hub_download(repo_id=LEGAL_DATASET_NAME, filename=filename, repo_type="dataset")


def load_content_by_id() -> dict[str, str]:
    path = get_parquet_path(f"data/{LEGAL_DATASET_CONTENT_CONFIG}.parquet")
    table = pq.read_table(path, columns=["id", "content_html"])
    return {
        str(row["id"]): row["content_html"]
        for row in table.to_pylist()
        if row.get("content_html")
    }


def load_relationships_by_doc_id() -> dict[str, list[dict[str, str]]]:
    path = get_parquet_path(f"data/{LEGAL_DATASET_RELATIONSHIPS_CONFIG}.parquet")
    table = pq.read_table(path, columns=["doc_id", "other_doc_id", "relationship"])
    relationships: dict[str, list[dict[str, str]]] = {}
    for row in table.to_pylist():
        doc_id = str(row["doc_id"])
        relationships.setdefault(doc_id, []).append(
            {
                "other_doc_id": str(row["other_doc_id"]),
                "relationship": row["relationship"] or "",
            }
        )
    return relationships


def build_chunk_records(row: dict, content_html: str, relationships: list[dict[str, str]]) -> list[dict]:
    doc_id = str(row["id"])
    content_text = clean_html_text(content_html)
    if not content_text:
        return []

    chunks = split_legal_chunks(
        content_text,
        max_chars=LEGAL_CHUNK_MAX_CHARS,
        article_threshold=LEGAL_ARTICLE_CHAPTER_THRESHOLD,
    )
    valid_chunks = [chunk for chunk in chunks if str(chunk.get("content_text", "") or "").strip()]
    total_chunks = len(valid_chunks)
    records = []
    for chunk_index, chunk in enumerate(valid_chunks):
        chunk_text = str(chunk.get("content_text", "") or "")
        records.append(
            {
                "id": f"{doc_id}:{chunk_index}",
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "content_text": chunk_text,
                "chapter_label": chunk.get("chapter_label"),
                "article_label": chunk.get("article_label"),
                "chunk_level": chunk.get("chunk_level"),
                "title": row.get("title", ""),
                "so_ky_hieu": row.get("so_ky_hieu", "") or "",
                "loai_van_ban": row.get("loai_van_ban", "") or "",
                "co_quan_ban_hanh": row.get("co_quan_ban_hanh", "") or "",
                "tinh_trang_hieu_luc": row.get("tinh_trang_hieu_luc", "") or "",
                "linh_vuc": row.get("linh_vuc", "") or "",
                "nganh": row.get("nganh", "") or "",
                "source_url": build_vbpl_source_url(doc_id),
                "relationships": relationships,
            }
        )
    return records


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Vietnamese legal documents into Qdrant")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N metadata documents")
    parser.add_argument("--reset-checkpoint", action="store_true", help="Ignore existing checkpoint and start from 0")
    parser.add_argument(
        "--start-index",
        type=int,
        default=None,
        dest="start_index",
        help="Starting metadata index (inclusive). When set, default checkpoint is ignored.",
    )
    parser.add_argument(
        "--end-index",
        type=int,
        default=None,
        dest="end_index",
        help="Ending metadata index (inclusive). Defaults to last document.",
    )
    parser.add_argument(
        "--checkpoint-path",
        type=str,
        default=None,
        dest="checkpoint_path",
        help="Path for checkpoint file (for parallel workers). Overrides the default path.",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        dest="worker_id",
        help="Worker identifier for isolated checkpoint files (e.g. '0', '1').",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print("=" * 60)
    print("Vietnamese Legal Documents Ingestion Script")
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
        print(f"Starting at explicit --start-index: {start_index}")

    print("\nLoading metadata from HuggingFace...")
    metadata_rows = load_dataset(LEGAL_DATASET_NAME, LEGAL_DATASET_METADATA_CONFIG, split=LEGAL_DATASET_SPLIT)
    total_documents = len(metadata_rows)

    # Respect --end-index if provided
    end_index = args.end_index if args.end_index is not None else total_documents - 1

    # Guard against empty or reversed ranges
    if end_index < start_index:
        print(f"\nRange [{start_index}, {end_index}] is empty — nothing to process.")
        return

    end_index = min(end_index, total_documents - 1)

    print(f"Metadata loaded: {total_documents} documents")
    print(f"Processing range: [{start_index}, {end_index}] (inclusive)")

    print("Loading content parquet directly...")
    content_by_id = load_content_by_id()
    print(f"Content rows available: {len(content_by_id)}")

    print("Loading relationships parquet directly...")
    relationships_by_doc_id = load_relationships_by_doc_id()
    print(f"Relationship groups available: {len(relationships_by_doc_id)}")

    print(f"\nEnsuring Qdrant collection '{QDRANT_COLLECTION_NAME}' exists...")
    client = get_qdrant_client()
    ensure_collection_exists(client)

    batch_size = INGEST_BATCH_SIZE
    pending_records: list[dict] = []
    processed_documents = 0

    for i in range(start_index, end_index + 1):
        row = metadata_rows[i]
        doc_id = str(row["id"])
        content_html = content_by_id.get(doc_id, "")
        if not content_html:
            continue

        pending_records.extend(
            build_chunk_records(
                row=row,
                content_html=content_html,
                relationships=relationships_by_doc_id.get(doc_id, []),
            )
        )
        processed_documents += 1

        should_flush = len(pending_records) >= batch_size
        reached_limit = args.limit is not None and processed_documents >= args.limit
        at_end = i == end_index
        if not should_flush and not reached_limit and not at_end:
            continue

        if pending_records:
            print(f"\nUpserting {len(pending_records)} chunks after metadata index {i}")
            ingest_articles(pending_records, batch_size=batch_size)
            last_record_id = pending_records[-1]["id"]
            save_checkpoint(i, last_record_id, checkpoint_path=checkpoint_path, worker_id=args.worker_id)
            print(f"  Checkpoint saved: index {i}, last chunk {last_record_id}")
            pending_records = []

        if reached_limit:
            break

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print(f"Metadata documents processed: {processed_documents}")
    print("=" * 60)


if __name__ == "__main__":
    main()
