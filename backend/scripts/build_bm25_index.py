"""Build (or rebuild) the BM25 index from the current Qdrant collection.

Usage:
    python -m scripts.build_bm25_index
    python -m scripts.build_bm25_index --output /custom/path.pkl
"""
import argparse
import logging

from services.bm25_index import build_index, save_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", default=None, help="Override BM25_INDEX_PATH")
    args = parser.parse_args()

    logger.info("Building BM25 index...")
    bm25, meta = build_index()
    save_index(bm25, meta, args.output)
    logger.info("Done. Indexed %d documents.", len(meta))


if __name__ == "__main__":
    main()