import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchText,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from core.config import (
    INGEST_BATCH_SIZE,
    INGEST_CONCURRENT_WORKERS,
    LEGAL_ARTICLE_CHAPTER_THRESHOLD,
    OLLAMA_EMBED_BATCH_SIZE,
    OLLAMA_EMBEDDING_MODEL,
    OLLAMA_EMBED_TIMEOUT,
    OLLAMA_URL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)
from html.parser import HTMLParser


class HTMLLegalParser:
    """Parser for Vietnamese legal HTML documents."""

    CHAPTER_PATTERNS = (
        re.compile(r"(?im)^\s*(Chương\s+[IVXLCDM0-9]+[^\n]*)\s*$"),
        re.compile(r"(?im)^\s*<h[1-6][^>]*>[^<]*Chương\s+[IVXLCDM0-9]+[^\n]*</h[1-6]>"),
    )
    ARTICLE_PATTERNS = (
        re.compile(r"(?im)^\s*(Điều\s+\d+)[.:]?\s*"),
        re.compile(r"(?im)^\s*<h[1-6][^>]*>[^<]*Điều\s+\d+[^\n]*</h[1-6]>"),
    )
    KHOAN_PATTERNS = (
        re.compile(r"(?im)^\s*Khoản\s+(\d+)[^\n]*"),
        re.compile(r"(?im)^\s*<p[^>]*>[^<]*Khoản\s+(\d+)[^\n]*</p>"),
        re.compile(r"(?im)^\s*(\d+)\.\s+[A-ZÀ-ỹ]"),
    )

    def __init__(self) -> None:
        self._headings: list[dict[str, Any]] = []
        self._paragraphs: list[str] = []
        self._raw_texts: list[str] = []
        self._current_data: str = ""
        self._current_tag: str = ""
        self._current_attrs: dict[str, str] = {}
        self._in_body: bool = False

    def parse(self, html: str) -> dict[str, Any]:
        """Parse HTML and extract semantic structure."""
        self._headings = []
        self._paragraphs = []
        self._raw_texts = []
        self._in_body = False

        parser = _HTMLLegalParserImpl(self)
        parser.feed(html)

        chapters = self._extract_by_pattern(self.CHAPTER_PATTERNS)
        articles = self._extract_by_pattern(self.ARTICLE_PATTERNS)
        khoans = self._extract_by_pattern(self.KHOAN_PATTERNS)

        return {
            "headings": self._headings,
            "paragraphs": self._paragraphs,
            "chapters": chapters,
            "articles": articles,
            "khoans": khoans,
            "raw_texts": self._raw_texts,
        }

    def _extract_by_pattern(self, patterns: tuple) -> list[dict[str, Any]]:
        results = []
        for pattern in patterns:
            for text in self._raw_texts:
                match = pattern.search(text)
                if match:
                    results.append({"text": match.group(1).strip(), "level": 0})
        return results

    def get_structured_chunks(self, max_chars: int = 1200) -> list[dict[str, Any]]:
        """Return chunks respecting semantic boundaries."""
        chunks = []
        current_chapter = None
        current_article = None
        current_khoan = None
        current_content = ""

        def flush_content(chunk_level: str = "paragraph") -> None:
            nonlocal current_content
            if not current_content:
                return
            if len(current_content) <= max_chars:
                chunks.append({
                    "content_text": current_content.strip(),
                    "chapter_label": current_chapter,
                    "article_label": current_article,
                    "khoan_label": current_khoan,
                    "chunk_level": chunk_level,
                })
            else:
                sub_chunks = split_document_chunks(current_content, max_chars=max_chars)
                for sc in sub_chunks:
                    chunks.append({
                        "content_text": sc.strip(),
                        "chapter_label": current_chapter,
                        "article_label": current_article,
                        "khoan_label": current_khoan,
                        "chunk_level": chunk_level,
                    })
            current_content = ""

        for heading in self._headings:
            text = heading["text"]
            level = heading["level"]

            if any(p.search(text) for p in self.CHAPTER_PATTERNS):
                flush_content("sub_chapter" if current_content else "chapter")
                current_chapter = text
                current_article = None
                current_khoan = None

            elif any(p.search(text) for p in self.ARTICLE_PATTERNS):
                flush_content("sub_article" if current_article else "paragraph")
                current_article = text
                current_khoan = None

            elif any(p.search(text) for p in self.KHOAN_PATTERNS):
                flush_content("sub_khoan" if current_khoan else "paragraph")
                current_khoan = text

            else:
                flush_content("sub_article" if current_article else "paragraph")
                current_content = text

        if current_content:
            flush_content("sub_khoan" if current_khoan else ("sub_article" if current_article else "paragraph"))

        return [c for c in chunks if c["content_text"]]



class _HTMLLegalParserImpl(HTMLParser):
    def __init__(self, outer: HTMLLegalParser) -> None:
        super().__init__()
        self._outer = outer

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._outer._current_tag = tag
        self._outer._current_attrs = dict(attrs)
        if tag in ("body", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._outer._in_body = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("body", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6"):
            text = self._outer._current_data.strip()
            if text:
                self._outer._raw_texts.append(text)
                if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    level = int(tag[1])
                    self._outer._headings.append({"text": text, "level": level})
                elif tag in ("p", "div"):
                    self._outer._paragraphs.append(text)
            self._outer._current_data = ""
            self._outer._in_body = False

    def handle_data(self, data: str) -> None:
        if self._outer._in_body:
            self._outer._current_data += data


_EMBED_TIMEOUT_SECONDS = float(OLLAMA_EMBED_TIMEOUT)
_VBPL_INDEX_FIELDS = (
    "title",
    "so_ky_hieu",
    "loai_van_ban",
    "co_quan_ban_hanh",
    "tinh_trang_hieu_luc",
    "linh_vuc",
    "nganh",
    "source_url",
    "chapter_label",
    "article_label",
    "chunk_level",
)

_CHAPTER_PATTERN = re.compile(r"(?im)^\s*(Chương\s+[IVXLCDM0-9]+[^\n]*)\s*$")
_ARTICLE_PATTERN = re.compile(r"(?im)^\s*(Điều\s+\d+)[.:]?\s*")
_KHOAN_PATTERN = re.compile(r"(?im)^\s*Khoản\s+(\d+)[^\n]*")


def detect_doc_format(
    text: str,
    article_threshold: int = LEGAL_ARTICLE_CHAPTER_THRESHOLD,
) -> str:
    article_count = len(_ARTICLE_PATTERN.findall(text or ""))
    chapter_count = len(_CHAPTER_PATTERN.findall(text or ""))
    if article_count >= article_threshold or chapter_count > 0:
        return "law"
    return "decision"


def split_legal_chunks(
    text: str,
    max_chars: int = 1200,
    article_threshold: int = LEGAL_ARTICLE_CHAPTER_THRESHOLD,
) -> list[dict[str, str | None]]:
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

    # Use HTMLLegalParser when HTML structure is detected
    if "<" in normalized_text and ">" in normalized_text:
        try:
            parser = HTMLLegalParser()
            result = parser.parse(normalized_text)
            if result["headings"] or result["khoans"]:
                return _split_with_html_parser(parser, max_chars)
        except Exception:
            pass

    # Fall back to regex-based chunking with khoan support
    return _split_by_legal_structure(normalized_text, max_chars, article_threshold)


def _split_with_html_parser(
    parser: HTMLLegalParser,
    max_chars: int,
) -> list[dict[str, str | None]]:
    """Split using HTMLLegalParser's structured approach."""
    return parser.get_structured_chunks(max_chars)


def _split_by_legal_structure(
    normalized_text: str,
    max_chars: int,
    article_threshold: int,
) -> list[dict[str, str | None]]:
    """Regex-based splitting with khoan support."""
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

    def split_paragraph_chunks(
        content: str,
        chapter_label: str | None = None,
        article_label: str | None = None,
        khoan_label: str | None = None,
        chunk_level: str = "paragraph",
    ) -> list[dict[str, str | None]]:
        return [
            build_chunk(chunk, chapter_label, article_label, khoan_label, chunk_level)
            for chunk in split_document_chunks(content, max_chars=max_chars)
        ]

    if detect_doc_format(normalized_text, article_threshold=article_threshold) != "law":
        return split_paragraph_chunks(normalized_text)

    article_matches = list(_ARTICLE_PATTERN.finditer(normalized_text))
    chapter_matches = list(_CHAPTER_PATTERN.finditer(normalized_text))
    khoan_matches = list(_KHOAN_PATTERN.finditer(normalized_text))

    if not article_matches:
        if not chapter_matches:
            return split_paragraph_chunks(normalized_text)

        return _split_by_chapters(
            normalized_text, chapter_matches, max_chars, build_chunk, split_paragraph_chunks
        )

    return _split_by_articles(
        normalized_text, article_matches, chapter_matches, khoan_matches,
        max_chars, build_chunk, split_paragraph_chunks
    )


def _split_by_chapters(
    normalized_text: str,
    chapter_matches: list,
    max_chars: int,
    build_chunk: callable,
    split_paragraph_chunks: callable,
) -> list[dict[str, str | None]]:
    """Split text by chapters when no articles are found."""
    chunks: list[dict[str, str | None]] = []
    for index, chapter_match in enumerate(chapter_matches):
        chapter_label = chapter_match.group(1).strip()
        chapter_start = chapter_match.start()
        chapter_end = chapter_matches[index + 1].start() if index + 1 < len(chapter_matches) else len(normalized_text)
        chapter_text = normalized_text[chapter_start:chapter_end].strip()
        if not chapter_text:
            continue

        if len(chapter_text) <= max_chars:
            chunks.append(build_chunk(chapter_text, chapter_label=chapter_label, chunk_level="chapter"))
            continue

        chunks.extend(
            split_paragraph_chunks(
                chapter_text,
                chapter_label=chapter_label,
                chunk_level="sub_chapter",
            )
        )

    if chunks:
        return [chunk for chunk in chunks if chunk["content_text"]]

    return split_paragraph_chunks(normalized_text)


def _split_by_articles(
    normalized_text: str,
    article_matches: list,
    chapter_matches: list,
    khoan_matches: list,
    max_chars: int,
    build_chunk: callable,
    split_paragraph_chunks: callable,
) -> list[dict[str, str | None]]:
    """Split text by articles, respecting khoan boundaries."""
    chunks: list[dict[str, str | None]] = []

    for index, article_match in enumerate(article_matches):
        article_label = article_match.group(1).strip()
        article_start = article_match.start()
        article_end = article_matches[index + 1].start() if index + 1 < len(article_matches) else len(normalized_text)
        article_text = normalized_text[article_start:article_end].strip()
        if not article_text:
            continue

        chapter_label = None
        for chapter_match in chapter_matches:
            if chapter_match.start() <= article_start:
                chapter_label = chapter_match.group(1).strip()
            else:
                break

        # Find khoans within this article
        article_khoans = [
            m for m in khoan_matches
            if article_start <= m.start() < article_end
        ]

        if not article_khoans:
            # No khoans, split by paragraphs
            if len(article_text) <= max_chars:
                chunks.append(build_chunk(article_text, chapter_label, article_label, None, "article"))
            else:
                chunks.extend(
                    split_paragraph_chunks(
                        article_text,
                        chapter_label=chapter_label,
                        article_label=article_label,
                        chunk_level="sub_article",
                    )
                )
            continue

        # Split by khoans
        for khoan_index, khoan_match in enumerate(article_khoans):
            khoan_label = khoan_match.group(1).strip()
            khoan_start = khoan_match.start()
            khoan_end = article_khoans[khoan_index + 1].start() if khoan_index + 1 < len(article_khoans) else article_end
            # Include article header in khoan text
            khoan_text = normalized_text[article_start:khoan_end].strip()
            if not khoan_text:
                continue

            if len(khoan_text) <= max_chars:
                chunks.append(build_chunk(khoan_text, chapter_label, article_label, khoan_label, "khoan"))
            else:
                chunks.extend(
                    split_paragraph_chunks(
                        khoan_text,
                        chapter_label=chapter_label,
                        article_label=article_label,
                        khoan_label=khoan_label,
                        chunk_level="sub_khoan",
                    )
                )

    if chunks:
        return [chunk for chunk in chunks if chunk["content_text"]]

    return split_paragraph_chunks(normalized_text)




def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=300)


def ensure_collection_exists(client: QdrantClient) -> None:
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if QDRANT_COLLECTION_NAME in collection_names:
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )

    for field_name in _VBPL_INDEX_FIELDS:
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION_NAME,
            field_name=field_name,
            field_schema="keyword",
        )


def clean_html_text(content_html: str) -> str:
    normalized = re.sub(r"<\s*br\s*/?>", "\n", content_html, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/p\s*>", "\n\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/div\s*>", "\n\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/tr\s*>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<\s*/h[1-6]\s*>", "\n\n", normalized, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", normalized)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_document_chunks(text: str, max_chars: int = 1200) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(start + max_chars, len(paragraph))
                chunks.append(paragraph[start:end].strip())
                start = end
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = paragraph

    if current:
        chunks.append(current)

    return [chunk for chunk in chunks if chunk]


def build_vbpl_source_url(doc_id: str) -> str:
    return f"https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID={doc_id}"


def _normalize_text_for_embedding(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"\s+", " ", ascii_text).strip()
    return ascii_text or (text or "")


def embed_texts(texts: list[str], task_type: str | None = None) -> list[list[float]]:
    if not texts:
        return []

    url = f"{OLLAMA_URL.rstrip('/')}/api/embed"
    model = OLLAMA_EMBEDDING_MODEL
    sub_batch_size = OLLAMA_EMBED_BATCH_SIZE
    results = []

    for i in range(0, len(texts), sub_batch_size):
        sub = texts[i:i + sub_batch_size]
        payload_input: str | list[str] = sub[0] if len(sub) == 1 else sub
        normalized_payload_input: str | list[str] = (
            _normalize_text_for_embedding(sub[0]) if len(sub) == 1 else [_normalize_text_for_embedding(item) for item in sub]
        )
        used_normalized_fallback = False
        for attempt in range(10):
            try:
                with httpx.Client(timeout=_EMBED_TIMEOUT_SECONDS) as client:
                    response = client.post(
                        url,
                        json={"model": model, "input": normalized_payload_input if used_normalized_fallback else payload_input},
                    )
                    response.raise_for_status()
                    data = response.json()
                    batch = data.get("embeddings") or ([data["embedding"]] if data.get("embedding") else [])
                    if not batch:
                        raise ValueError(f"Ollama returned no embeddings for {len(sub)} texts")
                    results.extend(batch)
                    break
            except (httpx.HTTPStatusError, ValueError) as exc:
                is_server_500 = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 500
                if is_server_500 and not used_normalized_fallback:
                    used_normalized_fallback = True
                    print("  [embed fallback] retrying with ASCII-normalized text")
                    continue
                if attempt == 9:
                    raise
                is_oom = is_server_500
                wait = min(60, 10 ** attempt) if is_oom else min(30, 2 ** attempt)
                print(f"  [embed retry {attempt + 1}/10] {exc} — waiting {wait}s")
                time.sleep(wait)

    return results


def ingest_articles(articles: list[dict], batch_size: int | None = None) -> None:
    if batch_size is None:
        batch_size = INGEST_BATCH_SIZE
    client = get_qdrant_client()
    workers = INGEST_CONCURRENT_WORKERS

    def _embed_and_build(article: dict) -> PointStruct:
        vector = embed_texts([article["content_text"]], task_type="RETRIEVAL_DOCUMENT")[0]
        raw_id = str(article["id"])
        point_id = str(uuid5(NAMESPACE_URL, f"vbpl:{raw_id}"))
        return PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "content_text": article["content_text"],
                "title": article["title"],
                "doc_id": article["doc_id"],
                "chunk_index": article["chunk_index"],
                "so_ky_hieu": article.get("so_ky_hieu", ""),
                "loai_van_ban": article.get("loai_van_ban", ""),
                "co_quan_ban_hanh": article.get("co_quan_ban_hanh", ""),
                "tinh_trang_hieu_luc": article.get("tinh_trang_hieu_luc", ""),
                "linh_vuc": article.get("linh_vuc", ""),
                "nganh": article.get("nganh", ""),
                "source_url": article["source_url"],
                "chapter_label": article.get("chapter_label"),
                "article_label": article.get("article_label"),
                "chunk_level": article.get("chunk_level", "paragraph"),
                "total_chunks": article.get("total_chunks"),
                "relationships": article.get("relationships", []),
            },
        )

    points = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_embed_and_build, art): art for art in articles}
        for future in as_completed(futures):
            points.append(future.result())

    max_retries = 5
    for attempt in range(max_retries):
        try:
            client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=points)
            return
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  [upsert retry {attempt + 1}/{max_retries}] {exc} — waiting {wait}s")
            time.sleep(wait)


def search_legal_context(
    message: str,
    filters: dict | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    client = get_qdrant_client()
    query_vector = embed_texts([message], task_type="RETRIEVAL_QUERY")[0]

    qdrant_filter = None
    if filters:
        conditions = []
        for field_name in ("loai_van_ban", "co_quan_ban_hanh", "linh_vuc", "nganh", "tinh_trang_hieu_luc"):
            if filters.get(field_name):
                conditions.append(
                    FieldCondition(
                        key=field_name,
                        match=MatchText(text=filters[field_name]),
                    )
                )
        if conditions:
            qdrant_filter = Filter(must=conditions)

    response = client.query_points(
        collection_name=QDRANT_COLLECTION_NAME,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
    )
    results: list[ScoredPoint] = list(response.points)

    return [
        {
            "content_text": point.payload.get("content_text", ""),
            "title": point.payload.get("title", ""),
            "source_url": point.payload.get("source_url", ""),
            "doc_id": point.payload.get("doc_id", ""),
            "chunk_index": point.payload.get("chunk_index", 0),
            "loai_van_ban": point.payload.get("loai_van_ban", ""),
            "co_quan_ban_hanh": point.payload.get("co_quan_ban_hanh", ""),
            "tinh_trang_hieu_luc": point.payload.get("tinh_trang_hieu_luc", ""),
            "chapter_label": point.payload.get("chapter_label"),
            "article_label": point.payload.get("article_label"),
            "chunk_level": point.payload.get("chunk_level", "paragraph"),
            "total_chunks": point.payload.get("total_chunks"),
            "relationships": point.payload.get("relationships", []),
            "score": point.score,
        }
        for point in results
    ]
