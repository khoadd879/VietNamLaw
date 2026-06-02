from pathlib import Path

import pytest

from services.prompt_loader import clear_cache, load_prompt

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def test_load_prompt_returns_markdown_content() -> None:
    clear_cache()
    content = load_prompt("lawyer_persona_v1")
    assert isinstance(content, str)
    assert "luật sư tư vấn pháp luật Việt Nam" in content
    assert "loi_chao" in content  # JSON schema key
    assert "disclaimer" in content


def test_load_prompt_uses_lru_cache() -> None:
    clear_cache()
    first = load_prompt("lawyer_persona_v1")
    second = load_prompt("lawyer_persona_v1")
    assert first is second  # same object -> cached


def test_load_prompt_missing_raises_file_not_found() -> None:
    clear_cache()
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist_v1")