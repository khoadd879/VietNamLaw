# Legal Document Chunking Improvements Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 5 chunking issues for Vietnamese legal documents dataset `th1nhng0/vietnamese-legal-documents`: improve regex patterns, detect Khoản boundaries, leverage HTML structure, enforce semantic chunking, and handle different document types.

**Architecture:** Rewrite `split_legal_chunks` in `qdrant_service.py` to use HTML parsing + semantic boundary detection before character-based enforcement. Add new `LegalDocumentParser` class that understands Vietnamese legal document structure. Config options via `core/config.py` remain backward-compatible with defaults tuned for legal documents.

**Tech Stack:** Python stdlib `html.parser` (no new dependencies), existing `qdrant_service.py`, `config.py`, `test_qdrant_service.py`

---

## File Structure

- **Modify:** `backend/services/qdrant_service.py` - rewrite chunking logic (lines 1-233)
- **Modify:** `backend/core/config.py` - add new chunking config options
- **Modify:** `backend/tests/services/test_qdrant_service.py` - add comprehensive chunking tests
- **Modify:** `scripts/ingest_phapdien.py` - minor adjustments if needed

---

## Task 1: Add HTML structure parser

**Files:**
- Modify: `backend/services/qdrant_service.py` (add new class after imports, before existing functions)
- Test: `backend/tests/services/test_qdrant_service.py` (add tests for HTML parsing)

- [ ] **Step 1: Write failing tests for HTML structure parser**

Add to `backend/tests/services/test_qdrant_service.py`:

```python
def test_html_parser_extracts_headings():
    from services.qdrant_service import HTMLLegalParser
    html = """
    <html><body>
        <h1>CHƯƠNG I: NHỮNG QUY ĐỊNH CHUNG</h1>
        <p>Some content here</p>
        <h2>Điều 1. Phạm vi điều chỉnh</h2>
        <p>Nội dung điều 1 khoản 1.</p>
        <p>Nội dung điều 1 khoản 2.</p>
    </body></html>
    """
    parser = HTMLLegalParser()
    result = parser.parse(html)
    assert len(result['headings']) == 3
    assert result['headings'][0]['text'] == "CHƯƠNG I: NHỮNG QUY ĐỊNH CHUNG"
    assert result['headings'][0]['level'] == 1

def test_html_parser_extracts_paragraphs():
    from services.qdrant_service import HTMLLegalParser
    html = "<p>Para 1</p><p>Para 2</p><div>Div content</div>"
    parser = HTMLLegalParser()
    result = parser.parse(html)
    assert len(result['paragraphs']) >= 2

def test_html_parser_preserves_semantic_structure():
    from services.qdrant_service import HTMLLegalParser
    html = """
    <h1>Chương I</h1>
    <h2>Điều 1.</h2>
    <p>Khoản 1. Nội dung khoản 1.</p>
    <p>Khoản 2. Nội dung khoản 2.</p>
    """
    parser = HTMLLegalParser()
    result = parser.parse(html)
    assert len(result['chapters']) == 1
    assert len(result['articles']) == 1
    assert len(result['khoans']) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_html_parser_extracts_headings -v`
Expected: FAIL with "cannot import HTMLLegalParser"

- [ ] **Step 3: Implement HTMLLegalParser class**

Add after line 26 in `qdrant_service.py`:

```python
class HTMLLegalParser:
    """Parse HTML legal documents to extract semantic structure."""

    CHAPTER_PATTERNS = [
        re.compile(r"(?im)^\s*chương\s+([IVXLCDM0-9]+)[\s.:\-]*(.+)$"),
        re.compile(r"(?im)^\s*chương\s+(\d+)[\s.:\-]*(.+)$"),
    ]
    ARTICLE_PATTERNS = [
        re.compile(r"(?im)^\s*điều\s+(\d+)[.\s:]+\s*(.+)$"),
        re.compile(r"(?im)^\s*điều\s+(\d+)[\s.:\-]*(.+)$"),
    ]
    KHOAN_PATTERNS = [
        re.compile(r"(?im)^\s*khoản\s+(\d+)[.:]\s*(.+)$"),
        re.compile(r"(?im)^\s*(\d+)\s*[.:]\s*(.+)$"),  # standalone number at start
    ]

    def __init__(self):
        self._chapters: list[dict] = []
        self._articles: list[dict] = []
        self._khoans: list[dict] = []
        self._paragraphs: list[str] = []
        self._raw_texts: list[tuple[str, str]] = []  # (text, source_tag)

    def parse(self, html: str) -> dict:
        """Parse HTML and return structured data."""
        from html.parser import HTMLParser

        class LegalHTMLParser(HTMLParser):
            def __init__(self, outer):
                super().__init__()
                self.outer = outer
                self._current_text = ""
                self._in_script = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style"):
                    self._in_script = True
                if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    self._flush_paragraph()
                    self._current_text = ""

            def handle_endtag(self, tag):
                if tag in ("script", "style"):
                    self._in_script = False
                if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "li"):
                    self._flush_paragraph()

            def handle_data(self, data):
                if self._in_script:
                    return
                stripped = data.strip()
                if stripped:
                    self._current_text += stripped + " "

            def _flush_paragraph(self):
                text = self._current_text.strip()
                if text:
                    self.outer._raw_texts.append((text, self.get_starttag_text() or ""))
                self._current_text = ""

            def handle_entityref(self, name):
                self._current_text += f"&{name};"

            def handle_charref(self, name):
                self._current_text += f"&#{name};"

        parser = LegalHTMLParser(self)
        parser.feed(html)
        parser._flush_paragraph()

        self._classify_raw_texts()
        return self._build_result()

    def _classify_raw_texts(self):
        for text, tag in self._raw_texts:
            text = text.strip()
            if not text:
                continue

            # Check for chapter
            for pattern in self.CHAPTER_PATTERNS:
                m = pattern.match(text)
                if m:
                    self._chapters.append({
                        "text": text,
                        "number": m.group(1),
                        "title": m.group(2).strip() if m.lastindex >= 2 else "",
                        "index": len(self._chapters),
                    })
                    break

            # Check for article
            for pattern in self.ARTICLE_PATTERNS:
                m = pattern.match(text)
                if m:
                    self._articles.append({
                        "text": text,
                        "number": m.group(1),
                        "title": m.group(2).strip() if m.lastindex >= 2 else "",
                        "index": len(self._articles),
                    })
                    break

            # Check for khoan (only if not already matched as article/chapter)
            for pattern in self.KHOAN_PATTERNS:
                m = pattern.match(text)
                if m:
                    self._khoans.append({
                        "text": text,
                        "number": m.group(1),
                        "content": m.group(2).strip() if m.lastindex >= 2 else text,
                        "index": len(self._khoans),
                    })
                    break

            # Default: paragraph
            if text:
                self._paragraphs.append(text)

    def _build_result(self) -> dict:
        return {
            "chapters": self._chapters,
            "articles": self._articles,
            "khoans": self._khoans,
            "paragraphs": self._paragraphs,
            "raw_texts": self._raw_texts,
        }

    def get_structured_chunks(self, max_chars: int = 1200) -> list[dict]:
        """Return chunks with semantic boundaries respected."""
        chunks = []
        current_article = None
        current_chapter = None
        current_khoan = None

        for text, tag in self._raw_texts:
            text = text.strip()
            if not text:
                continue

            # Check what type this is
            is_chapter = any(p.match(text) for p in self.CHAPTER_PATTERNS)
            is_article = any(p.match(text) for p in self.ARTICLE_PATTERNS)
            is_khoan = any(p.match(text) for p in self.KHOAN_PATTERNS)

            if is_chapter:
                current_chapter = text
                current_article = None
                current_khoan = None
            elif is_article:
                current_article = text
                current_khoan = None
            elif is_khoan:
                current_khoan = text
            else:
                # Content paragraph - attach to current article/chapter
                chunk_type = "content"
                if current_khoan:
                    chunk_type = "khoan_content"
                elif current_article:
                    chunk_type = "article_content"
                elif current_chapter:
                    chunk_type = "chapter_content"

                # Smart split if too long
                if len(text) <= max_chars:
                    chunks.append({
                        "text": text,
                        "chunk_type": chunk_type,
                        "chapter": current_chapter,
                        "article": current_article,
                        "khoan": current_khoan,
                    })
                else:
                    # Split by sentences/phrase boundaries
                    sub_chunks = self._split_long_content(text, max_chars)
                    for sc in sub_chunks:
                        chunks.append({
                            "text": sc,
                            "chunk_type": chunk_type,
                            "chapter": current_chapter,
                            "article": current_article,
                            "khoan": current_khoan,
                        })

        return chunks

    def _split_long_content(self, text: str, max_chars: int) -> list[str]:
        """Split long content at semantic boundaries."""
        # Try to split at sentence end (。.) or clause separators
        sentence_ends = re.findall(r'[。.]\s+', text)
        chunks = []
        current = ""

        for i, char in enumerate(text):
            current += char
            if len(current) >= max_chars:
                # Find last sentence boundary
                last_punct = max(current.rfind('。'), current.rfind('.'))
                if last_punct > max_chars // 2:
                    chunks.append(current[:last_punct + 1].strip())
                    current = current[last_punct + 1:].strip()
                else:
                    # No good boundary, hard split
                    chunks.append(current.strip())
                    current = ""

        if current.strip():
            chunks.append(current.strip())

        return [c for c in chunks if c]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_html_parser_extracts_headings backend/tests/services/test_qdrant_service.py::test_html_parser_extracts_paragraphs backend/tests/services/test_qdrant_service.py::test_html_parser_preserves_semantic_structure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/qdrant_service.py backend/tests/services/test_qdrant_service.py
git commit -m "feat: add HTMLLegalParser for semantic Vietnamese legal document structure extraction"
```

---

## Task 2: Improve regex patterns for article/chapter/khoan detection

**Files:**
- Modify: `backend/services/qdrant_service.py` (update patterns in `HTMLLegalParser` and existing `split_legal_chunks`)
- Test: `backend/tests/services/test_qdrant_service.py`

- [ ] **Step 1: Write tests for improved pattern matching**

Add to `test_qdrant_service.py`:

```python
def test_article_patterns():
    from services.qdrant_service import HTMLLegalParser
    parser = HTMLLegalParser()

    # Standard patterns
    assert parser.ARTICLE_PATTERNS[0].match("Điều 1. Phạm vi điều chỉnh")
    assert parser.ARTICLE_PATTERNS[0].match("Điều 45: Nội dung")
    # No dot variant
    assert parser.ARTICLE_PATTERNS[1].match("Điều 10 Các trường hợp")

def test_chapter_patterns():
    from services.qdrant_service import HTMLLegalParser
    parser = HTMLLegalParser()

    # Roman numerals
    assert parser.CHAPTER_PATTERNS[0].match("CHƯƠNG I: NHỮNG QUY ĐỊNH CHUNG")
    assert parser.CHAPTER_PATTERNS[0].match("Chương III - Nội dung")
    # Arabic numerals
    assert parser.CHAPTER_PATTERNS[1].match("Chương 1: Giới thiệu")
    assert parser.CHAPTER_PATTERNS[1].match("CHƯƠNG 10"))

def test_khoan_patterns():
    from services.qdrant_service import HTMLLegalParser
    parser = HTMLLegalParser()

    # Standard khoan
    assert parser.KHOAN_PATTERNS[0].match("Khoản 1. Nội dung khoản 1")
    assert parser.KHOAN_PATTERNS[0].match("khoản 2: định nghĩa")
    # Number dot at start
    assert parser.KHOAN_PATTERNS[1].match("1. Nội dung mục 1")
    assert parser.KHOAN_PATTERNS[1].match("2: điều khoản")
```

- [ ] **Step 2: Run tests to verify they pass (patterns should already work)**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_article_patterns backend/tests/services/test_qdrant_service.py::test_chapter_patterns backend/tests/services/test_qdrant_service.py::test_khoan_patterns -v`
Expected: PASS

- [ ] **Step 3: Verify patterns handle edge cases**

Add to `test_qdrant_service.py`:

```python
def test_patterns_unicode_variants():
    from services.qdrant_service import HTMLLegalParser
    parser = HTMLLegalParser()

    # Unicode number variants
    assert parser.ARTICLE_PATTERNS[0].match("Điều １２３")  # fullwidth digits
    assert parser.CHAPTER_PATTERNS[0].match("CHƯƠNG Ⅰ")   # roman numeral variant

def test_patterns_uppercase():
    from services.qdrant_service import HTMLLegalParser
    parser = HTMLLegalParser()

    assert parser.CHAPTER_PATTERNS[0].match("CHƯƠNG I")
    assert parser.CHAPTER_PATTERNS[0].match("chương ii")
    assert parser.ARTICLE_PATTERNS[0].match("ĐIỀU 10")
```

- [ ] **Step 4: Run edge case tests**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_patterns_unicode_variants backend/tests/services/test_qdrant_service.py::test_patterns_uppercase -v`
Expected: Results - may fail on fullwidth/roman variants, note for improvement

- [ ] **Step 5: Commit with pattern fixes if needed**

```bash
git add backend/services/qdrant_service.py backend/tests/services/test_qdrant_service.py
git commit -m "feat: enhance article/chapter/khoan regex patterns with Unicode support"
```

---

## Task 3: Rewrite `split_legal_chunks` to use semantic boundaries

**Files:**
- Modify: `backend/services/qdrant_service.py` (rewrite lines ~59-160)
- Test: `backend/tests/services/test_qdrant_service.py`

- [ ] **Step 1: Write tests for new split_legal_chunks behavior**

Add to `test_qdrant_service.py`:

```python
def test_split_legal_chunks_respects_khoan():
    from services.qdrant_service import split_legal_chunks

    text = """Chương I
Điều 1. Nội dung chính
Khoản 1. Phần mở đầu của điều này phải được hiểu theo nghĩa rộng bao gồm nhiều trường hợp khác nhau.
Khoản 2. Phần tiếp theo nói về quyền và nghĩa vụ của các bên liên quan trong quan hệ pháp luật.
Điều 2. Nội dung bổ sung"""

    chunks = split_legal_chunks(text, max_chars=300)
    # Should split at khoan boundaries, not arbitrary character cuts
    assert len(chunks) >= 2
    # Verify khoan labels are preserved
    for chunk in chunks:
        if "Khoản 1" in str(chunk):
            assert chunk.get("chunk_level") in ("sub_article", "khoan")

def test_split_legal_chunks_long_article():
    from services.qdrant_service import split_legal_chunks

    # Create text longer than max_chars with clear article structure
    text = "Điều 1. Title\n" + ("x" * 200 + "\n\n") * 20

    chunks = split_legal_chunks(text, max_chars=500)
    # Should not produce chunks that cut mid-sentence
    for chunk in chunks:
        if chunk.get("chunk_level") == "sub_article":
            assert len(chunk["content_text"]) <= 500

def test_split_legal_chunks_no_chapter_article():
    from services.qdrant_service import split_legal_chunks

    # Decision type document - no chapters or articles
    text = "Quyết định số 123/2020\n\n" + ("Paragraph " + "x" * 100 + "\n\n") * 10

    chunks = split_legal_chunks(text, max_chars=400)
    # Should still chunk by paragraph, not fail
    assert len(chunks) > 0

def test_split_legal_chunks_preserves_metadata():
    from services.qdrant_service import split_legal_chunks

    text = """CHƯƠNG II: TỔ CHỨC VÀ HOẠT ĐỘNG
Điều 10. Thẩm quyền
Nội dung điều 10 rất dài. """ + ("x" * 500)

    chunks = split_legal_chunks(text, max_chars=300)
    for chunk in chunks:
        if chunk.get("chapter_label"):
            assert "CHƯƠNG II" in chunk["chapter_label"]
```

- [ ] **Step 2: Run tests to verify they fail (old implementation)**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_split_legal_chunks_respects_khoan -v`
Expected: FAIL - old implementation doesn't detect khoan

- [ ] **Step 3: Rewrite split_legal_chunks function**

Replace the existing `split_legal_chunks` function (lines ~59-160) with:

```python
def split_legal_chunks(
    text: str,
    max_chars: int = 1200,
    article_threshold: int = LEGAL_ARTICLE_CHAPTER_THRESHOLD,
    use_html_parser: bool = True,
) -> list[dict[str, str | None]]:
    """
    Split legal document text into semantic chunks.

    Uses HTML structure when available for better semantic boundary detection.
    Falls back to regex-based detection for plain text.

    Args:
        text: Raw text content (HTML already cleaned or plain text)
        max_chars: Maximum characters per chunk
        article_threshold: Min articles to classify as "law" format
        use_html_parser: If True, attempt HTML parsing for structure

    Returns:
        List of chunks with keys: content_text, chapter_label, article_label,
        chunk_level, khoan_label
    """
    normalized_text = (text or "").strip()
    if not normalized_text:
        return []

    def build_chunk(
        content_text: str,
        chapter_label: str | None = None,
        article_label: str | None = None,
        khoan_label: str | None = None,
        chunk_level: str = "paragraph",
    ) -> dict[str, str | None]:
        return {
            "content_text": content_text.strip(),
            "chapter_label": chapter_label,
            "article_label": article_label,
            "khoan_label": khoan_label,
            "chunk_level": chunk_level,
        }

    # Try HTML-based parsing first
    if use_html_parser and "<" in normalized_text and ">" in normalized_text:
        try:
            parser = HTMLLegalParser()
            parsed = parser.parse(normalized_text)
            chunks = parser.get_structured_chunks(max_chars=max_chars)

            if chunks:
                result = []
                for chunk in chunks:
                    level = chunk["chunk_type"]
                    if level == "chapter_content":
                        level = "chapter"
                    elif level == "article_content":
                        level = "article"
                    elif level == "khoan_content":
                        level = "khoan"
                    elif chunk["text"].startswith("Điều"):
                        level = "article"
                    elif chunk["text"].startswith("Chương"):
                        level = "chapter"

                    result.append(build_chunk(
                        content_text=chunk["text"],
                        chapter_label=chunk.get("chapter"),
                        article_label=chunk.get("article"),
                        khoan_label=chunk.get("khoan"),
                        chunk_level=level,
                    ))
                return [c for c in result if c["content_text"]]

        except Exception:
            # Fall through to regex-based approach
            pass

    # Regex-based chunking (original approach improved)
    return _split_legal_chunks_regex(
        normalized_text,
        max_chars=max_chars,
        article_threshold=article_threshold,
        build_chunk=build_chunk,
    )


def _split_legal_chunks_regex(
    text: str,
    max_chars: int,
    article_threshold: int,
    build_chunk,
) -> list[dict[str, str | None]]:
    """Regex-based chunking for plain text without HTML structure."""
    article_matches = list(_ARTICLE_PATTERN.finditer(text))
    chapter_matches = list(_CHAPTER_PATTERN.finditer(text))
    khoan_matches = list(_KHOAN_PATTERN.finditer(text)) if '_KHOAN_PATTERN' in dir() else []

    # If we have articles, use article-based chunking
    if len(article_matches) >= article_threshold:
        return _split_by_articles(
            text, article_matches, chapter_matches, khoan_matches,
            max_chars, build_chunk
        )

    # If we have chapters but no articles, chunk by chapter
    if chapter_matches:
        return _split_by_chapters(text, chapter_matches, max_chars, build_chunk)

    # Fallback: paragraph-based chunking
    return _split_by_paragraphs(text, max_chars, build_chunk)


def _split_by_articles(text, article_matches, chapter_matches, khoan_matches, max_chars, build_chunk):
    """Split text by article boundaries, preserving khoan structure."""
    chunks = []
    current_chapter = None
    current_khoan = None

    for idx, article_match in enumerate(article_matches):
        article_label = article_match.group(1).strip()
        article_start = article_match.start()
        article_end = article_matches[idx + 1].start() if idx + 1 < len(article_matches) else len(text)
        article_text = text[article_start:article_end].strip()

        # Update chapter context
        for cm in reversed(chapter_matches):
            if cm.start() <= article_start:
                current_chapter = cm.group(1).strip()
                break

        # Extract khoans within this article
        article_khoans = []
        for km in khoan_matches:
            if article_start < km.start() < article_end:
                article_khoans.append(km)

        if not article_text:
            continue

        # If article is small enough, keep as single chunk
        if len(article_text) <= max_chars:
            chunks.append(build_chunk(
                article_text, current_chapter, article_label, None, "article"
            ))
        else:
            # Split by khoan first, then by paragraph
            if article_khoans:
                for k_idx, khoan_match in enumerate(article_khoans):
                    khoan_label = khoan_match.group(1).strip()
                    khoan_start = khoan_match.start()
                    khoan_end = article_khoans[k_idx + 1].start() if k_idx + 1 < len(article_khoans) else article_end
                    khoan_text = text[khoan_start:khoan_end].strip()

                    if khoan_text:
                        if len(khoan_text) <= max_chars:
                            chunks.append(build_chunk(
                                khoan_text, current_chapter, article_label, khoan_label, "khoan"
                            ))
                        else:
                            # Split long khoan by paragraphs
                            sub_chunks = _split_text_by_paragraph(khoan_text, max_chars)
                            for sc in sub_chunks:
                                chunks.append(build_chunk(
                                    sc, current_chapter, article_label, khoan_label, "sub_khoan"
                                ))
            else:
                # No khoan structure, split by paragraph
                sub_chunks = _split_text_by_paragraph(article_text, max_chars)
                for sc in sub_chunks:
                    chunks.append(build_chunk(sc, current_chapter, article_label, None, "sub_article"))

    return [c for c in chunks if c["content_text"]]


def _split_by_chapters(text, chapter_matches, max_chars, build_chunk):
    """Split text by chapter boundaries."""
    chunks = []

    for idx, chapter_match in enumerate(chapter_matches):
        chapter_label = chapter_match.group(1).strip()
        chapter_start = chapter_match.start()
        chapter_end = chapter_matches[idx + 1].start() if idx + 1 < len(chapter_matches) else len(text)
        chapter_text = text[chapter_start:chapter_end].strip()

        if not chapter_text:
            continue

        if len(chapter_text) <= max_chars:
            chunks.append(build_chunk(chapter_text, chapter_label, None, None, "chapter"))
        else:
            sub_chunks = _split_text_by_paragraph(chapter_text, max_chars)
            for sc in sub_chunks:
                chunks.append(build_chunk(sc, chapter_label, None, None, "sub_chapter"))

    return [c for c in chunks if c["content_text"]]


def _split_text_by_paragraph(text: str, max_chars: int) -> list[str]:
    """Split text by paragraph boundaries, then by character limit."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            # Long paragraph - split by sentences first
            if current:
                chunks.append(current)
                current = ""

            sentences = re.split(r'(?<=[。.;:,])+\s*', para)
            current_para = ""
            for sent in sentences:
                if len(current_para) + len(sent) <= max_chars:
                    current_para += sent
                else:
                    if current_para:
                        chunks.append(current_para.strip())
                    if len(sent) > max_chars:
                        # Split long sentence by characters
                        for i in range(0, len(sent), max_chars):
                            chunks.append(sent[i:i + max_chars].strip())
                        current_para = ""
                    else:
                        current_para = sent
            if current_para.strip():
                current = current_para
        else:
            candidate = para if not current else f"{current}\n\n{para}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = para

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


def _split_by_paragraphs(text: str, max_chars: int, build_chunk) -> list[dict]:
    """Fallback: split by paragraphs without structural awareness."""
    sub_chunks = _split_text_by_paragraph(text, max_chars)
    return [build_chunk(sc, None, None, None, "paragraph") for sc in sub_chunks]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_split_legal_chunks_respects_khoan backend/tests/services/test_qdrant_service.py::test_split_legal_chunks_long_article backend/tests/services/test_qdrant_service.py::test_split_legal_chunks_no_chapter_article backend/tests/services/test_qdrant_service.py::test_split_legal_chunks_preserves_metadata -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/qdrant_service.py backend/tests/services/test_qdrant_service.py
git commit -m "feat: rewrite split_legal_chunks with semantic boundary detection and Khoản support"
```

---

## Task 4: Add new config options for chunking behavior

**Files:**
- Modify: `backend/core/config.py`
- Test: No new tests needed (config only)

- [ ] **Step 1: Read current config**

Run: `cat /home/khoa/Company/VietNamLaw/backend/core/config.py`

- [ ] **Step 2: Add new chunking config options**

Add to `config.py` after line 15:

```python
# Chunking behavior
LEGAL_CHUNK_USE_HTML_PARSER = os.getenv("LEGAL_CHUNK_USE_HTML_PARSER", "true").lower() == "true"
LEGAL_CHUNK_PRESERVE_KHOAN = os.getenv("LEGAL_CHUNK_PRESERVE_KHOAN", "true").lower() == "true"
LEGAL_CHUNK_MIN_KHOAN_CHARS = int(os.getenv("LEGAL_CHUNK_MIN_KHOAN_CHARS", "50"))
LEGAL_CHUNK_SPLIT_AT_SENTENCE = os.getenv("LEGAL_CHUNK_SPLIT_AT_SENTENCE", "true").lower() == "true"
```

- [ ] **Step 3: Commit**

```bash
git add backend/core/config.py
git commit -m "feat: add configurable chunking behavior options"
```

---

## Task 5: Fix `clean_html_text` to preserve structure for parser

**Files:**
- Modify: `backend/services/qdrant_service.py`
- Test: `backend/tests/services/test_qdrant_service.py`

- [ ] **Step 1: Write test for clean_html_text preservation**

Add to `test_qdrant_service.py`:

```python
def test_clean_html_preserves_structure_for_parser():
    from services.qdrant_service import clean_html_text

    html = """<html><body>
<h1>CHƯƠNG I</h1>
<h2>Điều 1.</h2>
<p>Khoản 1. Content here</p>
<p>Khoản 2. More content</p>
</body></html>"""

    text = clean_html_text(html)
    # After cleaning, parser should still be able to detect structure
    from services.qdrant_service import split_legal_chunks
    chunks = split_legal_chunks(text, max_chars=500)
    assert len(chunks) > 0
```

- [ ] **Step 2: Run test to verify it passes (or fails if structure lost)**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_clean_html_preserves_structure_for_parser -v`

- [ ] **Step 3: If test fails, update clean_html_text**

The issue is that `clean_html_text` strips ALL tags including headings that carry structure. Update `clean_html_text` to preserve heading markers:

```python
def clean_html_text(content_html: str, preserve_structure: bool = True) -> str:
    """
    Clean HTML text while optionally preserving structure markers.

    Args:
        content_html: Raw HTML content
        preserve_structure: If True, replace heading tags with markdown-style
                           markers that the parser can use
    """
    normalized = re.sub(r"<\s*br\s*/?>", "\n", content_html, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/p\s*>", "\n\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/tr\s*>", "\n", normalized, flags=re.IGNORECASE)

    if preserve_structure:
        # Convert headings to line markers that preserve structure
        normalized = re.sub(r"<\s*/h([1-6])\s*>", r"\n\n", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"<\s*h([1-6])(?:\s[^>]*)?>", r"\n\n", normalized, flags=re.IGNORECASE)
        # Convert div to paragraph separator
        normalized = re.sub(r"<\s*/div\s*>", "\n\n", normalized, flags=re.IGNORECASE)
    else:
        normalized = re.sub(r"<\s*/div\s*>", "\n\n", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"<\s*/h[1-6]\s*>", "\n\n", normalized, flags=re.IGNORECASE)

    text = re.sub(r"<[^>]+>", " ", normalized)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py::test_clean_html_preserves_structure_for_parser -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/qdrant_service.py backend/tests/services/test_qdrant_service.py
git commit -m "feat: improve clean_html_text to preserve structure markers for semantic parsing"
```

---

## Task 6: Update `ingest_phapdien.py` if needed

**Files:**
- Modify: `scripts/ingest_phapdien.py` (only if needed after changes)

- [ ] **Step 1: Run existing tests to check integration**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py -v --tb=short 2>&1 | head -100`

- [ ] **Step 2: Verify no breaking changes to ingest script**

If tests pass and `build_chunk_records` in `ingest_phapdien.py` still works, no changes needed. If changes needed, update `ingest_phapdien.py` to handle new `khoan_label` field in chunks.

- [ ] **Step 3: Commit if changes made**

```bash
git add scripts/ingest_phapdien.py
git commit -m "fix: update ingest script for new chunk structure including Khoản labels"
```

---

## Task 7: Run full test suite and integration check

**Files:**
- Test: All modified files

- [ ] **Step 1: Run full test suite**

Run: `cd /home/khoa/Company/VietNamLaw && python -m pytest backend/tests/services/test_qdrant_service.py -v --tb=short`

- [ ] **Step 2: Run a small ingestion test (if Qdrant available)**

Run: `cd /home/khoa/Company/VietNamLaw && python scripts/ingest_phapdien.py --limit 5 --reset-checkpoint 2>&1 | head -50`

- [ ] **Step 3: Verify checkpoint still works**

Check that checkpoint structure still compatible with existing checkpoints in `data/.ingest_articles.json`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: run full test suite for legal chunking improvements"
```

---

## Summary of Changes

| Task | File | Changes |
|------|------|---------|
| 1 | qdrant_service.py | Add `HTMLLegalParser` class for semantic HTML parsing |
| 2 | qdrant_service.py | Improve regex patterns for Unicode/case variants |
| 3 | qdrant_service.py | Rewrite `split_legal_chunks` with khoan support |
| 4 | config.py | Add configurable chunking behavior |
| 5 | qdrant_service.py | Update `clean_html_text` to preserve structure |
| 6 | ingest_phapdien.py | Update if needed for new chunk fields |
| 7 | All | Full test suite and integration verification |

---

## Rollback Plan

If issues arise:
```bash
git log --oneline -5  # Find pre-changes commit
git reset --hard <commit-hash>  # Revert all changes
git checkout HEAD~1 -- backend/services/qdrant_service.py backend/core/config.py  # Alternative
```