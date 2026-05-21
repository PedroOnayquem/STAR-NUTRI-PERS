from typing import Literal

from pydantic import BaseModel, Field


ReasoningLevel = Literal["low", "medium", "high", "ultra"]


class SendChatMessageRequest(BaseModel):
    patient_id: str | None = None
    session_id: str | None = None
    reasoning_level: ReasoningLevel = "medium"
    content: str = Field(min_length=1, max_length=4000)


class CreateChatSessionRequest(BaseModel):
    patient_id: str | None = None
    title: str | None = Field(default=None, max_length=120)
