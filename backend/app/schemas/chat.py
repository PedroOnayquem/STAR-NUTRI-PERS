from pydantic import BaseModel, Field


class SendChatMessageRequest(BaseModel):
    patient_id: str | None = None
    session_id: str | None = None
    content: str = Field(min_length=1, max_length=4000)


class CreateChatSessionRequest(BaseModel):
    patient_id: str | None = None
    title: str | None = Field(default=None, max_length=120)
