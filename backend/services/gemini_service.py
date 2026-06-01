from google import genai

from core.config import GEMINI_API_KEY, GEMINI_MODEL


def generate_answer(question: str, contexts: list[dict[str, str]]) -> str:
    if not GEMINI_API_KEY:
        return "Hệ thống chưa được cấu hình GEMINI_API_KEY."

    context_chunks = [item["content_text"] for item in contexts]
    context = "\n".join(context_chunks)
    prompt = (
        "Bạn là trợ lý pháp luật Việt Nam. Trả lời dựa trên ngữ cảnh dưới đây.\n"
        f"Ngữ cảnh:\n{context}\n\n"
        f"Câu hỏi: {question}"
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text or "Không có câu trả lời phù hợp."
