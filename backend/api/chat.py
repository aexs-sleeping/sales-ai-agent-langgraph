"""Chat + HITL SSE endpoints (PRD §3.2 / §3.3).

The LangGraph agent (`agent.graph.graph`) is imported lazily inside each handler
so that `/api/health` and `/api/conversations` (and server startup) work even
when the selected LLM provider is not configured. A failed import is surfaced
to the client as an SSE `error` event instead of crashing the worker.
"""

import logging
from typing import Any, Dict, Iterator, Optional, Tuple

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, ToolMessage

from api.conversations import build_config, upsert_conversation
from api.models import ChatRequest, DenyRequest
from api.sse import event_stream, format_sse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_response(generator: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(generator, media_type="text/event-stream", headers=SSE_HEADERS)


def _sse_error(error: Exception) -> StreamingResponse:
    """Return a single SSE `error` frame (used when the graph cannot be imported)."""
    message = f"{type(error).__name__}: {error}" if str(error) else repr(error)
    logger.error("Cannot initialize agent graph: %s", message)

    def gen() -> Iterator[str]:
        yield format_sse("error", {"message": message})

    return _sse_response(gen())


def _graph_or_error() -> Tuple[Any, Optional[StreamingResponse]]:
    """Lazily import the graph (PRD §3.1) or return an SSE `error` response.

    The import runs inside each handler so the server boots and `/api/health`
    and `/api/conversations` work without Google credentials. A failed import is
    surfaced to the client as an SSE error frame instead of crashing the worker.
    """
    try:
        from agent.graph import graph  # noqa: PLC0415 - required lazy import
    except Exception as e:  # noqa: BLE001 - graceful error event
        return None, _sse_error(e)
    return graph, None


def _conversation_config(conversation_id: str, customer_id: Optional[str] = None) -> dict:
    """Register/upsert the conversation and build its runtime config."""
    record = upsert_conversation(conversation_id, customer_id)
    return build_config(conversation_id, record["customer_id"])


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Run one user turn against the graph and stream the reply as SSE."""
    config = _conversation_config(req.conversation_id, req.customer_id)
    graph, error = _graph_or_error()
    if error is not None:
        return error
    graph_input: Dict[str, Any] = {"messages": [HumanMessage(content=req.message)]}
    return _sse_response(event_stream(graph, graph_input, config))


@router.post("/conversations/{conversation_id}/approve")
def approve(conversation_id: str) -> StreamingResponse:
    """Approve the pending sensitive tool call: resume the graph with None."""
    config = _conversation_config(conversation_id)
    graph, error = _graph_or_error()
    if error is not None:
        return error
    # Resuming with None re-runs the interrupted node (create_order) and streams the
    # follow-up assistant reply.
    return _sse_response(event_stream(graph, None, config))


@router.post("/conversations/{conversation_id}/deny")
def deny(conversation_id: str, body: DenyRequest) -> StreamingResponse:
    """Deny the pending sensitive tool call by injecting a ToolMessage."""
    config = _conversation_config(conversation_id)
    graph, error = _graph_or_error()
    if error is not None:
        return error

    snapshot = graph.get_state(config)
    if not snapshot.next:
        return _sse_error(ValueError("No pending approval for this conversation."))

    pending_tool_call = snapshot.values["messages"][-1].tool_calls[0]
    denial = ToolMessage(
        tool_call_id=pending_tool_call["id"],
        content=(
            f"API call denied by user. Reasoning: '{body.reason}'. "
            "Continue assisting, accounting for the user's input."
        ),
    )
    graph_input: Dict[str, Any] = {"messages": [denial]}
    return _sse_response(event_stream(graph, graph_input, config))
