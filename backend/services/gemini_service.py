from google import genai
from core.config import GEMINI_API_KEY, GEMINI_MODEL


def build_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n".join(context_chunks)
    return (
        "Bạn là trợ lý pháp luật Việt Nam. "
        "Chỉ dựa trên ngữ cảnh được cung cấp. "
        "Nếu ngữ cảnh không đủ, nói rõ là chưa đủ thông tin.\n\n"
        f"Ngữ cảnh:\n{context}\n\n"
        f"Câu hỏi: {question}"
    )


def generate_answer(question: str, contexts: list[dict[str, str]]) -> str:
    context_chunks = [item["content"] for item in contexts]
    prompt = build_prompt(question=question, context_chunks=context_chunks)
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text or "Không có câu trả lời phù hợp."