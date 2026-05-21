from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class AppMode(str, Enum):
    COAUTHOR = "coauthor"
    REVIEW = "review"
    ADAPT = "adapt"


class ChatMessageItem(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class Attachment(BaseModel):
    filename: str
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    conversation_history: list[ChatMessageItem] = Field(
        default_factory=list, alias="conversationHistory"
    )
    attachments: list[Attachment] = Field(default_factory=list)
    form_values: dict[str, Union[str, bool, list[str]]] = Field(
        default_factory=dict, alias="formValues"
    )
    mode: AppMode = AppMode.COAUTHOR

    model_config = {"populate_by_name": True}


class FieldUpdate(BaseModel):
    data_id: int = Field(..., alias="dataId")
    value: Union[str, bool, list[str]]

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    message: str
    field_updates: list[FieldUpdate] = Field(
        default_factory=list, alias="fieldUpdates"
    )

    model_config = {"populate_by_name": True}


class FlaggedIssue(BaseModel):
    data_id: int = Field(..., alias="dataId")
    severity: str
    message: str
    suggestion: Optional[str] = None

    model_config = {"populate_by_name": True}


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
