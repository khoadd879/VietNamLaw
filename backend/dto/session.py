from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionUpdateRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str


class MessageResponse(BaseModel):
    id: str
    session_id: str
    user_id: str
    role: str
    content: str
    sources_json: dict | None = None