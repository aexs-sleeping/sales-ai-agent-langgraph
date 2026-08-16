"""Pydantic request/response models for the FastAPI backend (PRD §3.2)."""

from typing import List

from pydantic import BaseModel, Field

# Default customer, matching the hardcoded customer_id in the Streamlit frontend.
DEFAULT_CUSTOMER_ID = "123456789"


class ChatRequest(BaseModel):
    """Body of `POST /api/chat`."""

    conversation_id: str
    message: str
    customer_id: str = DEFAULT_CUSTOMER_ID


class DenyRequest(BaseModel):
    """Body of `POST /api/conversations/{id}/deny`."""

    reason: str


class ConversationCreateResponse(BaseModel):
    """Response of `POST /api/conversations`."""

    status: str = "ok"
    conversation_id: str


class ConversationInfo(BaseModel):
    """One entry of the in-memory conversation list."""

    conversation_id: str
    customer_id: str
    created_at: str


class ConversationListResponse(BaseModel):
    """Response of `GET /api/conversations`."""

    status: str = "ok"
    conversations: List[ConversationInfo]
