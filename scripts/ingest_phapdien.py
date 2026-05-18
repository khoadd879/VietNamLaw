#!/usr/bin/env python3
"""
Ingestion script for phapdien-moj-gov-vn dataset.
Loads Vietnamese legal articles from HuggingFace, embeds via Gemini, upserts to Qdrant Cloud.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from datasets import load_dataset

from core.config import (
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    INGEST_BATCH_SIZE,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)
from services.qdrant_service import embed_texts, ensure_collection_exists, get_qdrant_client, ingest_articles


def get_checkpoint_path() -> Path:
    return Path(__file__).parent.parent / "data" / ".ingest_checkpoint.json"


def load_checkpoint() -> dict | None:
    """Load checkpoint if exists."""
    path = get_checkpoint_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_checkpoint(last_processed_index: int, last_processed_id: str) -> None:
    """Save checkpoint after each batch."""
    checkpoint = {
        "last_processed_index": last_processed_index,
        "last_processed_id": last_processed_id,
        "timestamp": datetime.now().isoformat(),
    }
    path = get_checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Ingest phapdien-moj-gov-vn dataset into Qdrant")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N articles (smoke test)")
    parser.add_argument("--reset-checkpoint", action="store_true", help="Ignore existing checkpoint and start from 0")
    args = parser.parse_args()

    print("=" * 60)
    print("phapdien-moj-gov-vn Ingestion Script")
    print("=" * 60)

    # Validate config
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)
    if not QDRANT_API_KEY:
        print("ERROR: QDRANT_API_KEY not set")
        sys.exit(1)

    # Check for checkpoint
    checkpoint = None if args.reset_checkpoint else load_checkpoint()
    start_index = 0
    if checkpoint:
        start_index = checkpoint["last_processed_index"] + 1
        print(f"Resuming from checkpoint: index {start_index}")
        print(f"Last processed ID: {checkpoint['last_processed_id']}")
        print(f"Checkpoint time: {checkpoint['timestamp']}")

    # Load dataset
    print("\nLoading dataset from HuggingFace...")
    dataset = load_dataset("tmquan/phapdien-moj-gov-vn", split="train")
    total_articles = len(dataset)
    print(f"Dataset loaded: {total_articles} articles")

    # Ensure collection exists
    print(f"\nEnsuring Qdrant collection '{QDRANT_COLLECTION_NAME}' exists...")
    client = get_qdrant_client()
    ensure_collection_exists(client)

    # Process articles
    articles_to_process = []
    for i in range(start_index, total_articles):
        row = dataset[i]
        content_text = row.get("content_text", "")

        # Skip empty content
        if not content_text or not content_text.strip():
            continue

        article = {
            "id": row.get("article_anchor", str(i)),
            "content_text": content_text,
            "article_title": row.get("article_title", ""),
            "article_anchor": row.get("article_anchor", ""),
            "topic_title": row.get("topic_title", ""),
            "topic_id": row.get("topic_id", ""),
            "demuc_title": row.get("demuc_title", ""),
            "demuc_id": row.get("demuc_id", ""),
            "source_url": row.get("source_url", ""),
        }
        articles_to_process.append(article)

        if args.limit is not None and len(articles_to_process) >= args.limit:
            break

    if args.limit is not None:
        print(f"Limit applied: {args.limit}")
    print(f"Articles to process: {len(articles_to_process)}")

    # Process in batches
    batch_size = INGEST_BATCH_SIZE
    total_batches = (len(articles_to_process) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        batch_start = batch_num * batch_size
        batch_end = min(batch_start + batch_size, len(articles_to_process))
        batch = articles_to_process[batch_start:batch_end]

        current_index = start_index + batch_start
        print(f"\nBatch {batch_num + 1}/{total_batches}")
        print(f"  Processing indices {current_index} to {current_index + len(batch) - 1}")

        # Ingest batch
        ingest_articles(batch, batch_size)

        # Save checkpoint
        last_article = batch[-1]
        save_checkpoint(current_index + len(batch) - 1, last_article["id"])
        print(f"  Checkpoint saved: index {current_index + len(batch) - 1}")

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print(f"Total articles processed: {len(articles_to_process)}")
    print("=" * 60)


if __name__ == "__main__":
    main()