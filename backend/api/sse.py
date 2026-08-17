"""SSE event generation for the FastAPI backend (PRD §3.3).

The event protocol is fixed by the PRD and consumed by the Vue frontend:

    event: message\n           data: {"content": "<token increment>"}
    event: tool_status\n       data: {"name": ..., "status": running|success|error, "args": ...?}
    event: approval_required\n data: {"tool_call": {"id", "name", "args"}}
    event: done\n              data: {}
    event: error\n             data: {"message": ...}

Each frame is terminated by a blank line: `event: <type>\ndata: <json>\n\n`.
"""

import json
import logging
from typing import Any, Dict, Iterator, List

from langchain_core.messages import AIMessageChunk, ToolMessage

from agent.utils import TOOL_ERROR_PREFIX

logger = logging.getLogger(__name__)


def format_sse(event: str, data: Any) -> str:
    """Serialize one SSE frame. json.dumps escapes control characters, so the
    `data:` line is always a single line regardless of payload content."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _message_chunk_text(chunk: AIMessageChunk) -> str:
    """Extract the incremental text carried by an AIMessageChunk."""
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            else:
                btype = (
                    block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                )
                btext = (
                    block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
                )
                if btype == "text" and btext:
                    parts.append(btext)
        return "".join(parts)
    return ""


def _tool_calls_from_chunks(chunks: List[AIMessageChunk]) -> List[dict]:
    """Return the tool calls of one assistant turn, merging the streaming chunks.

    The merge is skipped when no chunk carried tool-call data, which is the
    common case (plain-text replies), avoiding a full-turn copy just to read
    `merged.tool_calls`.
    """
    ai_chunks = [c for c in chunks if isinstance(c, AIMessageChunk)]
    if not ai_chunks:
        return []
    if not any(getattr(c, "tool_call_chunks", None) for c in ai_chunks):
        return []
    merged = ai_chunks[0]
    for chunk in ai_chunks[1:]:
        merged = merged + chunk
    return merged.tool_calls or []


def _tool_status_data(name: str, status: str, args: Any = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {"name": name, "status": status}
    if args is not None:
        data["args"] = args
    return data


def _emit_tool_running(
    chunks: List[AIMessageChunk], tool_calls_by_id: Dict[str, dict]
) -> Iterator[str]:
    """Emit `tool_status(running)` for every tool call in the previous assistant turn."""
    for tc in _tool_calls_from_chunks(chunks):
        tool_calls_by_id[tc["id"]] = {"name": tc["name"], "args": tc.get("args")}
        yield format_sse("tool_status", _tool_status_data(tc["name"], "running", tc.get("args")))


def _emit_tool_status(chunk: ToolMessage, tool_calls_by_id: Dict[str, dict]) -> Iterator[str]:
    """Emit `tool_status(success|error)` once a tool has produced its result.

    On success the tool's structured output (serialized JSON in the ToolMessage
    content) is attached as `result`, so the frontend can render product/order
    cards without scraping the assistant's reply text (PRD §3.3).
    """
    tc_id = getattr(chunk, "tool_call_id", None)
    info = tool_calls_by_id.get(tc_id, {})
    content = str(chunk.content)
    status = "error" if content.startswith(TOOL_ERROR_PREFIX) else "success"
    name = info.get("name") or getattr(chunk, "name", None) or "tool"
    data = _tool_status_data(name, status, info.get("args"))
    if status == "success":
        try:
            data["result"] = json.loads(content)
        except ValueError:
            # Every tool returns a dict, so non-JSON here is a contract
            # violation — log it loudly instead of silently dropping the cards.
            logger.warning(
                "tool_status(success) for %s carried non-JSON content: %.200s",
                name,
                content,
            )
    yield format_sse("tool_status", data)


def event_stream(graph, graph_input: Any, config: dict) -> Iterator[str]:
    """Run the compiled LangGraph with `stream_mode="messages"` and translate the
    emitted `(chunk, metadata)` tuples into SSE frames per the PRD protocol.

    - `graph_input` is `{"messages": [HumanMessage(...)]}` for a chat turn,
      `None` to resume an interrupted graph (approve), or
      `{"messages": [ToolMessage(...)]}` to resume with a denial (deny).
    - The caller is responsible for the lazy `from agent.graph import graph`
      so the server can boot without Google credentials.
    """
    tool_calls_by_id: Dict[str, dict] = {}
    current_step = None
    assistant_chunks: List[AIMessageChunk] = []

    try:
        for chunk, metadata in graph.stream(graph_input, config, stream_mode="messages"):
            chunk_step = metadata.get("langgraph_step")

            # A new node execution started: the previous assistant turn is complete.
            if chunk_step != current_step:
                yield from _emit_tool_running(assistant_chunks, tool_calls_by_id)
                assistant_chunks = []
                current_step = chunk_step

            if isinstance(chunk, AIMessageChunk):
                assistant_chunks.append(chunk)
                text = _message_chunk_text(chunk)
                if text:
                    yield format_sse("message", {"content": text})
            elif isinstance(chunk, ToolMessage):
                yield from _emit_tool_status(chunk, tool_calls_by_id)

        # Stream finished. If the last assistant turn ended in a tool call the
        # graph was interrupted before running it (sensitive tools / HITL). The
        # pending calls were already recorded by _emit_tool_running above.
        yield from _emit_tool_running(assistant_chunks, tool_calls_by_id)

        snapshot = graph.get_state(config)
        if snapshot.next and tool_calls_by_id:
            for tc_id, info in tool_calls_by_id.items():
                yield format_sse(
                    "approval_required",
                    {
                        "tool_call": {
                            "id": tc_id,
                            "name": info["name"],
                            "args": info.get("args"),
                        }
                    },
                )

        yield format_sse("done", {})

    except Exception as e:  # noqa: BLE001 - any failure becomes an error SSE event
        logger.exception("SSE stream failed")
        yield format_sse("error", {"message": str(e)})
