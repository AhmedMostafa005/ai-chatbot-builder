from pydantic import BaseModel, Field

class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    model: str = "models/gemini-2.5-flash"
    system_prompt: str = "Answer accurately using the provided knowledge when relevant. If unsure, say so."
    welcome_message: str = "Hello! How can I help?"
    primary_color: str = "#2563eb"
    allowed_domains: list[str] = []

class BotUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    welcome_message: str | None = None
    primary_color: str | None = None
    allowed_domains: list[str] | None = None
    published: bool | None = None

class ChatRequest(BaseModel):
    bot_id: str
    visitor_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=10000)

class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: list[str] = []
