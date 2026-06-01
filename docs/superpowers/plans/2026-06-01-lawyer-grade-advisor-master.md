# Lawyer-Grade Advisor — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển chatbot pháp luật Việt Nam hiện tại từ dạng "hỏi–đáp một lượt" (single-turn Q&A) sang dạng **luật sư tư vấn thật thụ**: hỏi thêm khi thiếu facts, phân tích điều luật, khuyến nghị phương án, cảnh báo rủi ro, dẫn nguồn chính xác.

**Architecture:** 3-Sprint roadmap xếp chồng (foundation → memory → advanced RAG). Mỗi Sprint ra mắt được một phiên bản **chạy được, demo được, test pass**. Sprint 1 thay prompt + history + structured output (không đổi schema DB). Sprint 2 thêm schema `case_facts` + `case_summary` + intake. Sprint 3 hybrid retrieval + multi-query + citation verification + UX chip trích dẫn.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + Neon Postgres (backend) · Next.js 14 + React + TypeScript + react-markdown (frontend) · Qdrant (vector) · Groq llama-3.1-8b-instant (LLM, key rotation) · Ollama bge-m3 (embeddings) · pytest (test).

---

## Tình trạng hiện tại (đã đối chiếu code 1/6/2026)

| Khả năng luật sư | Trạng thái | Bằng chứng |
|---|---|---|
| Hỏi thêm khi thiếu facts | ❌ | `chat_service.py:13-16` truyền thẳng message vào RAG, không có cơ chế clarification |
| Phân loại quan hệ pháp luật | ❌ | Prompt trong `groq_service.py:25` chỉ nói "Bạn là trợ lý pháp luật Việt Nam" |
| Tra cứu cơ sở pháp lý | ✅ một phần | `qdrant_service.py:610-658` trả về top_k vector results, payload có `loai_van_ban`/`linh_vuc` |
| Phân tích điều luật liên quan | 🟡 chunking tốt | `qdrant_service.py` đã chunk theo Điều/Khoản/Điểm, có `chapter_label`, `article_label`, `relationships[]` — **chưa** được tận dụng |
| Khuyến nghị + cảnh báo rủi ro | ❌ | Prompt không yêu cầu, response thường chỉ trả lời factual |
| Trích dẫn nguồn chính xác | 🟡 | Sources trả về chỉ là URL string, frontend `assistant-message.tsx:34-42` hiển thị chip tĩnh không click được |
| Stateless / không nhớ case | ❌ | `chat_service.py:11` lưu message nhưng `chat_service.py:16` không load history vào prompt |

**Kết luận:** Hệ thống đáp ứng **~1/5** yêu cầu tư vấn luật sư. Mạnh nhất ở chunking semantic. Yếu nhất ở tư vấn có chiều sâu (clarify → classify → research → analyze → recommend).

---

## Roadmap tổng quan

```
Sprint 1 (Foundation)          Sprint 2 (Case Memory)          Sprint 3 (Advanced RAG + UX)
─────────────────────          ────────────────────────         ─────────────────────────────
1.1 Prompt persona luật sư     2.1 Schema case_facts            3.1 Hybrid BM25 + vector
1.2 Pass history N=10          2.2 case_summary/case_type/      3.2 Multi-query expansion
1.3 Structured JSON output         conversation_phase           3.3 Citation verification
1.4 Retrieval guard            2.3 Fact-extractor service       3.4 Cross-ref relationships[]
1.5 Frontend render            2.4 Two-stage reasoning          3.5 LegalCitationChip UI
                               2.5 Intake form                  3.6 SuggestedFollowUps
                                                                3.7 DisclaimerBanner
```

| Sprint | Output demo được | Schema DB | Test mới | UI thay đổi |
|---|---|---|---|---|
| **1** | Bot trả lời đúng vai luật sư, có disclaimer, có 7-section structure, nhớ 10 lượt gần nhất, fallback an toàn khi không tìm thấy | Không đổi | 6 unit + 1 integration | Render JSON sections |
| **2** | Bot hỏi thêm facts, nhớ case xuyên suốt phiên, phân tích theo loại vụ | +3 cột `chat_sessions` + 1 bảng `case_facts` | 8 unit + 2 integration | Intake form lúc tạo session |
| **3** | Trích dẫn điều-khoản chính xác, gợi ý câu hỏi tiếp, banner cảnh báo | Không đổi | 6 unit + 1 E2E | Citation chip click, follow-ups, disclaimer |

---

## File structure (sau khi hoàn thành cả 3 sprint)

```
backend/
├── core/
│   └── config.py                       [Sprint 1] +SPRINT constants
├── entities/
│   ├── chat_session.py                 [Sprint 2] +case_type/case_summary/conversation_phase
│   └── case_fact.py                    [Sprint 2] NEW
├── repositories/
│   ├── case_facts.py                   [Sprint 2] NEW
│   └── messages.py                     [Sprint 2] +list_recent
├── services/
│   ├── groq_service.py                 [Sprint 1] system prompt, history, JSON mode, guard
│   ├── chat_service.py                 [Sprint 1+2] history, structured, fact-extract orchestration
│   ├── fact_extractor.py               [Sprint 2] NEW
│   ├── two_stage_reasoner.py           [Sprint 2] NEW
│   ├── bm25_index.py                   [Sprint 3] NEW
│   ├── citation_verifier.py            [Sprint 3] NEW
│   ├── crossref_walker.py              [Sprint 3] NEW
│   └── qdrant_service.py               [Sprint 3] +hybrid_search + multi_query
├── api/routes/
│   ├── chat.py                         [Sprint 1+2] new response shape
│   └── sessions.py                     [Sprint 2] +case_type on create
├── dto/
│   ├── chat.py                         [Sprint 1+2] new fields
│   └── case.py                         [Sprint 2] NEW
├── prompts/
│   ├── lawyer_persona_v1.md            [Sprint 1] NEW
│   ├── fact_extractor_v1.md            [Sprint 2] NEW
│   └── synthesizer_v1.md               [Sprint 2] NEW
└── tests/
    ├── services/
    │   ├── test_groq_service.py        [Sprint 1] rewrite
    │   ├── test_chat_service.py        [Sprint 1+2] new
    │   ├── test_fact_extractor.py      [Sprint 2] new
    │   └── test_bm25_index.py          [Sprint 3] new
    └── api/
        └── test_chat_endpoint.py       [Sprint 1+2+3] new

frontend/
├── lib/
│   ├── api.ts                          [Sprint 1+2+3] +StructuredResponse +CaseType
│   └── types.ts                        [Sprint 1+2+3] +LawyerSection
├── components/chat/
│   ├── assistant-message.tsx           [Sprint 1+3] render JSON sections
│   ├── legal-citation-chip.tsx         [Sprint 3] NEW
│   ├── suggested-follow-ups.tsx        [Sprint 3] NEW
│   ├── disclaimer-banner.tsx           [Sprint 3] NEW
│   └── intake-form.tsx                 [Sprint 2] NEW
└── app/
    └── chat/[sessionId]/page.tsx       [Sprint 2] intake on first message

docs/
└── superpowers/plans/
    ├── 2026-06-01-lawyer-grade-advisor-master.md  (file này)
    ├── 2026-06-01-lawyer-grade-advisor-sprint1-foundation.md
    ├── 2026-06-01-lawyer-grade-advisor-sprint2-case-memory.md
    └── 2026-06-01-lawyer-grade-advisor-sprint3-advanced-rag-ux.md
```

---

## Sub-plans (link)

1. **[Sprint 1 — Foundation](./2026-06-01-lawyer-grade-advisor-sprint1-foundation.md)**
   Prompt persona luật sư, pass history, structured JSON, retrieval guard, frontend renderer. **5 task, ~1 ngày.**

2. **[Sprint 2 — Case Memory](./2026-06-01-lawyer-grade-advisor-sprint2-case-memory.md)**
   `case_facts` table, `case_summary`/`case_type`/`conversation_phase` columns, fact-extractor, two-stage reasoning, intake form. **6 task, ~2 ngày.**

3. **[Sprint 3 — Advanced RAG + UX](./2026-06-01-lawyer-grade-advisor-sprint3-advanced-rag-ux.md)**
   Hybrid BM25 + vector, multi-query, citation verification, cross-ref walker, LegalCitationChip, SuggestedFollowUps, DisclaimerBanner. **7 task, ~2-3 ngày.**

---

## Nguyên tắc thực thi (áp dụng mọi sprint)

- **TDD thuần:** Mỗi task viết failing test trước → chạy để confirm fail → code minimal pass → refactor → commit.
- **Mỗi task = 1 commit.** Không commit cả ngày.
- **Branch-per-sprint:** `git checkout -b feat/sprint-N` từ main trước khi bắt đầu.
- **Không thay đổi ngoài phạm vi task:** Sprint 1 không được đụng schema, Sprint 3 không được đụng persona prompt.
- **Prompt = file Markdown, không hard-code:** Tất cả prompt nằm trong `backend/prompts/`. Cho phép iterate nhanh không cần redeploy.
- **Tiếng Việt trong UI, tiếng Anh trong code.** Comment code bằng tiếng Anh (match repo hiện tại).
- **Test phải nhanh:** Mock Groq client như pattern `test_groq_service.py` hiện tại. Không gọi thật Groq trong CI.
- **Commit message convention:** `feat:`, `test:`, `refactor:`, `docs:`, `fix:` — match hiện tại.

---

## Self-review checklist (chạy trước khi merge mỗi sprint)

- [ ] Tất cả test pass: `cd backend && pytest -v`
- [ ] Tất cả test frontend pass: `cd frontend && npm test` (nếu có)
- [ ] Không có file mới nào lớn hơn 300 dòng (split nếu vượt)
- [ ] Migration Alembic chạy thẳng trên Neon dev: `alembic upgrade head`
- [ ] Smoke test thủ công: tạo session → gửi 1 câu hỏi factual → nhận JSON 7-section → click vào source chip → load lại history đúng.
- [ ] README (nếu có) update với output mới.

---

## Out of scope (cố ý không làm)

- Streaming token-by-token (SSE) — để Sprint 4.
- Multi-user collaborative sessions — không yêu cầu.
- Voice input/output — không yêu cầu.
- Auto-update knowledge base — manual ingest vẫn dùng `scripts/ingest_phapdien.py` hiện có.
- i18n English — chỉ tiếng Việt.
- Auth/RBAC nâng cao — JWT hiện tại đủ.

---

## Estimated effort

| Sprint | Task count | TDD time | Smoke test | Total |
|---|---|---|---|---|
| 1 | 5 | 6h | 1h | **1 ngày** |
| 2 | 6 | 14h | 2h | **~2 ngày** |
| 3 | 7 | 18h | 3h | **~3 ngày** |
| **Tổng** | **18** | **38h** | **6h** | **~6 ngày làm việc** |
