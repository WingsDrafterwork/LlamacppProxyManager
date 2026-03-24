from pydantic import BaseModel

class ChatMessage(BaseModel):
    user: str
    content: str
    timestamp: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str
