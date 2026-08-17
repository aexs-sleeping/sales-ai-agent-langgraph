# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Virtual Sales Agent: a **FastAPI backend + Vue 3 frontend** application whose core is a LangGraph state machine driven by Google Vertex AI (`gemini-2.0-flash-exp` via `langchain-google-vertexai`), with a MySQL store database (SQLAlchemy Core + pymysql) and optional LangSmith tracing. Its signature feature is human-in-the-loop approval: order creation is a "sensitive" tool, and the graph interrupts for explicit user approval before executing it. A legacy Streamlit client (`backend/main.py`) still exists but is superseded by the Vue frontend.

There are no tests, no linter/formatting config, and no CI in this repo.

Roadmap (decided with the owner): multi-provider LLM support (a `DEEPSEEK_API_KEY` already sits in the local `.env` but no code consumes it yet). Payment (Alipay/WeChat) is deferred.

## Commands

```bash
# One-time setup (README requires Python 3.12+; use the py launcher explicitly,
# the default `python` on PATH may be 3.10)
py -3.12 -m venv venv
venv\Scripts\activate            # Windows; source venv/bin/activate on Linux/Mac
# pip uses the Tsinghua mirror on this machine (owner's preference):
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Environment: copy env-example to .env and fill in keys
# GOOGLE_API_KEY, GOOGLE_APPLICATION_CREDENTIALS, GCP_PROJECT_ID, REGION,
# LangSmith keys for tracing, MYSQL_HOST/PORT/USER/PASSWORD/DB, DEEPSEEK_API_KEY
# (database config raises a clear error if MYSQL_PASSWORD is missing)

# Initialize MySQL DB (CREATE DATABASE + schema + seed data) — run from the repo root
python backend/setup_database.py

# Backend API — run from the repo root (main_fastapi inserts backend/ onto sys.path)
venv\Scripts\python -m uvicorn backend.main_fastapi:app --port 8000
# port overridable via API_PORT or PORT env

# Frontend (Vue 3) — separate terminal; Vite proxies /api → http://localhost:8000
cd frontend
npm install
npm run dev                     # dev server on :5173
npm run build                   # type-check (vue-tsc) + production build

# Legacy Streamlit client (transitional, still present)
streamlit run backend/main.py
```

Env vars must be set before launching the backend: `graph.py` calls `load_dotenv()` at import time and copies them into `os.environ`. The `.env` file lives only at the repo root; a fresh checkout or git worktree lacks it.

## Development Workflow (owner's rules — mandatory)

- **Never develop directly on `main`.** Branch model: `main` (stable) ← `dev` (integration) ← `feature/<name>` (one branch per feature).
- **One commit per feature update** — each feature branch should carry exactly one commit.
- Push the feature branch, then **stop and ask the owner for review**; merge into `dev` (`git merge --no-ff`) only after they approve.
- **Never open a PR unless the owner explicitly asks for one.**
- Independent features may be developed in parallel by sub-agents in isolated worktrees, each on its own feature branch.

## Architecture

### Layout and imports

All Python code lives under `backend/`, which acts as the **import root**: the FastAPI entry imports `from api.xxx`, the API layer imports `from agent.graph import graph` (lazily) and `from database.db_manager import ...`, and agent modules import each other as `agent.tools` / `agent.utils`. Keep this convention — do not import as `backend.xxx`. `backend/main_fastapi.py` inserts `backend/` onto `sys.path` so `uvicorn backend.main_fastapi:app` resolves `api.*` / `agent.*`; `backend/main.py` and `backend/setup_database.py` land on `sys.path` by being run by path.

The Vue frontend lives in `frontend/` (Vite + Vue 3 + TypeScript) and is fully decoupled — it talks only to the FastAPI HTTP/SSE API.

File paths are anchored to `Path(__file__)` (`backend/database/config.py`, `backend/main.py`), never to the current working directory. Commands are still run from the repo root because `.env` lives there and `load_dotenv()` searches the cwd.

### LangGraph graph (`backend/agent/graph.py`)

`State` = `{messages: Annotated[list[AnyMessage], add_messages], user_info: str}`.

- Nodes: `assistant` → conditional edge `route_tools` → `safe_tools` or `sensitive_tools` → back to `assistant`. All tool nodes use `create_tool_node_with_fallback` from `utils.py`, which wraps `ToolNode` so exceptions become a `ToolMessage` (content prefixed `Error:` — see `TOOL_ERROR_PREFIX`) instead of crashing the graph.
- Compiled with `MemorySaver` checkpointer and `interrupt_before=["sensitive_tools"]`. The interrupt is the entire HITL mechanism: the graph pauses before running a sensitive tool and resumes via `graph.invoke(None, config)`.
- Conversation state is per-session, keyed on `configurable.thread_id` in the runtime config. The config shape everywhere is `{"configurable": {"customer_id": str, "thread_id": str}}` — `customer_id` is threaded into `State.user_info` by the `Assistant` node and read by tools.
- The `Assistant` node re-prompts ("Respond with a real output.") if the LLM returns an empty response.

### Tools (`backend/agent/tools.py`)

Five `@tool`-decorated functions, split in `graph.py`:

- **Safe (run immediately):** `get_available_categories`, `search_products`, `search_products_recommendations`, `check_order_status`
- **Sensitive (interrupted for approval):** `create_order`

Tools that need customer context declare `*, config: RunnableConfig` — LangGraph injects the runtime config automatically. All DB access goes through `DatabaseManager` (`backend/database/db_manager.py`). `create_order` wraps its inserts in an explicit transaction with rollback on error and decrements product `Quantity`.

### FastAPI backend (`backend/main_fastapi.py`, `backend/api/`)

- `backend/main_fastapi.py`: FastAPI app, CORS (`http://localhost:5173/5174`), `GET /api/health`, uvicorn entry (`API_PORT`/`PORT`, default 8000), `sys.path` bootstrap.
- `backend/api/models.py`: pydantic request/response models (`ChatRequest`, `DenyRequest`, conversation responses, `DEFAULT_CUSTOMER_ID = "123456789"`).
- `backend/api/conversations.py`: in-memory `CONVERSATIONS` dict (`conversation_id == thread_id`), `build_config()`, `POST|GET /api/conversations`.
- `backend/api/chat.py`: `POST /api/chat`, `POST /api/conversations/{id}/approve`, `POST /api/conversations/{id}/deny`. All three **lazily import `agent.graph` inside the handler** (`_graph_or_error()`), so the server boots and health/conversations work without Google credentials.
- `backend/api/sse.py`: SSE event generator translating `graph.stream(..., stream_mode="messages")` `(chunk, metadata)` tuples into the PRD protocol.

**SSE event protocol (frontend contract — `backend/api/sse.py` + `frontend/src/api/sse.ts`):**
| event | data | meaning |
|---|---|---|
| `message` | `{content}` | AI reply token increment |
| `tool_status` | `{name, status: running\|success\|error, args?}` | tool lifecycle; error detected via the `TOOL_ERROR_PREFIX` in `agent/utils.py` |
| `approval_required` | `{tool_call: {id, name, args}}` | graph interrupted before `create_order`; derived from the already-merged `tool_calls_by_id` |
| `done` / `error` | `{}` / `{message}` | stream end / failure (any exception becomes an `error` frame, never a crash) |

**HITL over HTTP:** chat streams until `approval_required` + `done`; the client then calls `approve` (resume with `None`) or `deny` (inject a `ToolMessage` with a reason, matching the old Streamlit flow). Conversation state is **process-local** (MemorySaver + `CONVERSATIONS` dict) and lost on restart.

### Vue 3 frontend (`frontend/`)

- Vite + Vue 3 + TypeScript + Pinia + Element Plus (zh-CN locale, brand `#1E6FFF`), icons registered individually in `src/main.ts` (tree-shaking).
- `src/api/sse.ts`: `@microsoft/fetch-event-source` POST+SSE transport shared by chat / approve / deny; normalizes failures into `handlers.onError`. `src/api/client.ts`: REST helpers (`createConversation`, shared `parseError`).
- `src/stores/chat.ts`: Pinia store with one active stream at a time — `runStream()` is the shared setup/teardown for the three actions; `appendContent` writes through a cached message object reference (no per-token array scan).
- Components under `src/components/`: `chat/` (ChatView, ChatMessage, MessageInput, ToolStatusBar, WelcomeEmpty), `products/ProductCard`, `orders/OrderCard`, `approval/ApprovalCard` (approve/deny + reason dialog), `layout/ChatSidebar` (new conversation, clear).
- `src/utils/toolLabels.ts` is the single source for tool name → Chinese labels; `src/utils/parse.ts` reconstructs product/order cards from the assistant reply (see gotcha).
- Vite dev proxy: `/api` → `http://localhost:8000`.

### Streamlit client (`backend/main.py`) — legacy, transitional

Still functional and usable as a fallback: session state holds `messages`, a per-session `thread_id`, and `config` with `customer_id` hardcoded to `"123456789"`. Its HITL flow (stream → `get_state` → approve/deny via `invoke`) is the same mechanism the FastAPI layer now exposes over HTTP.

### Database layer (`backend/database/`, `backend/db/`)

- MySQL (local service `MySQL97`, MySQL 9.7) accessed via SQLAlchemy Core (`mysql+pymysql://`); database name defaults to `store` (utf8mb4).
- `backend/database/config.py`: `DatabaseConfig` dataclass; `get_config()` loads the repo-root `.env` itself and reads `MYSQL_HOST/PORT/USER/PASSWORD/DB`, **raising a clear error if `MYSQL_PASSWORD` is missing** — credentials are never hardcoded. Also pins schema/seed paths (`backend/db/schemas.sql`, `backend/db/products.json`, anchored to `Path(__file__)`). Change paths here, not in callers.
- `backend/database/db_manager.py`: `DatabaseManager` with two context managers — `get_connection()` for reads, `transaction()` (`engine.begin()`, commit on success / rollback on error) for writes. `create_database()` does `CREATE DATABASE IF NOT EXISTS` + executes the schema (statements split on `;`). `insert_products_from_json` loads via pandas and **lowercases** `product_name`/`category` (keys: `product_name`, `category`, `description`, `price`, `quantity`).
- `backend/setup_database.py`: creates DB + schema, seeds demo customer `123456789` (matches the hardcoded `customer_id`), seeds products only when the table is empty (idempotent).
- `backend/db/schemas.sql`: MySQL dialect (`AUTO_INCREMENT`, CHECK constraints — enforced on MySQL ≥ 8.0.16); creates `customers` (fixes the old dangling FK).

## Gotchas

- **LLM provider selection:** `agent/llm.py::get_llm()` picks the model by `LLM_PROVIDER` (default `gemini`); the gemini path reads `GCP_PROJECT_ID` (with `PROJECT_ID` fallback — the historical mismatch is resolved). With `LLM_PROVIDER=deepseek` no Google credentials are needed at all.
- **No tool results in the SSE protocol (open contract decision):** `tool_status` carries only `name/status/args`. The frontend therefore reconstructs product/order cards by scraping JSON out of the assistant reply text (`frontend/src/utils/parse.ts`). A proposed `result` field on `tool_status(success)` would let the backend stream structured tool output and delete most of `parse.ts` — discussed with the owner, **not merged**.
- **Provider credentials gate real chat:** the graph raises a clear `ValueError` when the selected provider's credentials are missing (`GCP_PROJECT_ID`/`REGION` for gemini, `DEEPSEEK_API_KEY` for deepseek). The FastAPI layer lazy-imports the graph, so the server boots and `/api/health`/`/api/conversations` work regardless, while `/api/chat` emits an `error` SSE frame until the provider (and the DB) are configured.
- **Process-local conversation state:** MemorySaver + the in-memory `CONVERSATIONS` dict are lost on restart; there is no persistence yet.
- `route_tools` and the approval flows (both Streamlit `main.py` and the FastAPI `deny` endpoint) assume a **single tool call** per AI message (`tool_calls[0]`); parallel tool calls are not handled.
- `.gitignore` ignores `*.db` and `*.json`; `backend/db/products.json` is tracked only because it predates the rule, and `frontend/.gitignore` adds `!` negations so `package.json`/`tsconfig*.json`/lockfiles are committed. New JSON data files outside those exceptions are silently ignored.
- Tools run raw SQL through SQLAlchemy `text()` with `:named` params; rows must be fetched via `.mappings()` — bare `text()` rows are positional-only and string indexing raises `TypeError`.
- MySQL runs with `ONLY_FULL_GROUP_BY`: every `GROUP BY` query must list all selected non-aggregated columns (see `check_order_status`).
- MySQL FKs **are enforced** (unlike the old SQLite setup): `create_order` will fail if the customer doesn't exist in `customers` (seeded by `setup_database.py`).
- A git worktree (used for parallel feature branches) has no `.env`, so running the backend there degrades `/api/chat` to an SSE error until `.env` is copied in.
