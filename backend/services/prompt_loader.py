"""Load and cache prompt templates from disk."""
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=16)
def load_prompt(name: str) -> str:
    """Load a prompt template by filename (without .md suffix).

    Cached so repeated calls within a request are O(1) after the first.
    Raises FileNotFoundError if the prompt does not exist.
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def clear_cache() -> None:
    """Clear the LRU cache. Useful in tests."""
    load_prompt.cache_clear()