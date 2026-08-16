"""Conversation registry + REST routes (PRD §3.2).

In-memory session table: `conversation_id -> {customer_id, created_at}`.
`conversation_id` doubles as the LangGraph `thread_id` for the MemorySaver
checkpointer, so state survives across requests while the process is alive.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

from api.models import (
    DEFAULT_CUSTOMER_ID,
    ConversationCreateResponse,
    ConversationListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["conversations"])

# In-memory conversation registry (lost on restart, per MVP scope).
CONVERSATIONS: dict[str, dict] = {}


def build_config(conversation_id: str, customer_id: str) -> dict:
    """Build the LangGraph runtime config keyed on the conversation thread."""
    return {
        "configurable": {
            "thread_id": conversation_id,
            "customer_id": customer_id,
        }
    }


def register_conversation(
    conversation_id: str, customer_id: str = DEFAULT_CUSTOMER_ID
) -> dict:
    """Register or update a conversation entry under an explicit id."""
    record = {
        "conversation_id": conversation_id,
        "customer_id": customer_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    CONVERSATIONS[conversation_id] = record
    return record


def upsert_conversation(
    conversation_id: str, customer_id: Optional[str] = None
) -> dict:
    """Return the existing conversation, or register a new one for this id."""
    record = CONVERSATIONS.get(conversation_id)
    if record is None:
        record = register_conversation(conversation_id, customer_id or DEFAULT_CUSTOMER_ID)
    return record


@router.post("/conversations", response_model=ConversationCreateResponse)
def create_conversation() -> ConversationCreateResponse:
    """Create a new conversation and return its id (used as thread_id)."""
    conversation_id = str(uuid.uuid4())
    register_conversation(conversation_id)
    logger.info("Created conversation %s", conversation_id)
    return ConversationCreateResponse(conversation_id=conversation_id)


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations() -> ConversationListResponse:
    """List in-memory conversations (basic metadata, MVP scope)."""
    items = [
        {
            "conversation_id": rec["conversation_id"],
            "customer_id": rec["customer_id"],
            "created_at": rec["created_at"],
        }
        for rec in CONVERSATIONS.values()
    ]
    return ConversationListResponse(conversations=items)
