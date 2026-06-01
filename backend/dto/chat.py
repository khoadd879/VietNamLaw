from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] | None = None
    structured: dict | None = None
    case_brief: dict | None = None


class IntakeFact(BaseModel):
    key: str
    value: str


class IntakeRequest(BaseModel):
    session_id: str
    case_type: str
    case_summary: str
    initial_facts: list[IntakeFact] = []


class IntakeFactOut(BaseModel):
    key: str
    value: str
    confidence: float


class IntakeResponse(BaseModel):
    session_id: str
    case_type: str
    case_summary: str
    facts: list[IntakeFactOut]