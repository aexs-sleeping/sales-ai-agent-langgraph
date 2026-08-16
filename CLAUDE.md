# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Virtual Sales Agent: a Python 3.12+ Streamlit chatbot backed by a LangGraph state machine using Google Vertex AI (`gemini-2.0-flash-exp` via `langchain-google-vertexai`), with a MySQL store database (SQLAlchemy Core + pymysql) and optional LangSmith tracing. Its signature feature is human-in-the-loop approval: order creation is a "sensitive" tool, and the graph interrupts for explicit user approval before executing it.

There are no tests, no linter/formatting config, and no CI in this repo.

Roadmap (decided with the owner, not started): split into FastAPI backend + Vue 3 frontend, multi-provider LLM support (DeepSeek etc.). Payment (Alipay/WeChat) is deferred.

## Commands

```bash
# One-time setup (README requires Python 3.12+; use the py launcher explicitly,
# the default `python` on PATH may be 3.10)
py -3.12 -m venv venv
venv\Scripts\activate            # Windows; source venv/bin/activate on Linux/Mac
# pip uses the Tsinghua mirror on this machine (owner's preference):
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Environment: copy env-example to .env and fill in keys
# (README calls it ".env-example" but the actual file is env-example)
# GOOGLE_API_KEY, GOOGLE_APPLICATION_CREDENTIALS, GCP_PROJECT_ID, REGION,
# LangSmith keys for tracing, plus MYSQL_HOST/PORT/USER/PASSWORD/DB
# (database config raises a clear error if MYSQL_PASSWORD is missing)

# Initialize MySQL DB (CREATE DATABASE + schema + seed data) — run from the repo root
python backend/setup_database.py

# Run the app (opens browser at localhost:8501) — run from the repo root
streamlit run backend/main.py
```

Env vars must be set before launching: `graph.py` calls `load_dotenv()` at import time and copies them into `os.environ`.

## Development Workflow (owner's rules — mandatory)

- **Never develop directly on `main`.** Branch model: `main` (stable) ← `dev` (integration) ← `feature/<name>` (one branch per feature).
- **One commit per feature update** — each feature branch should carry exactly one commit.
- Push the feature branch, then **stop and ask the owner for review**; merge into `dev` (`git merge --no-ff`) only after they approve.
- **Never open a PR unless the owner explicitly asks for one.**
- Independent features may be developed in parallel by sub-agents in isolated worktrees, each on its own feature branch.

## Architecture

### Layout and imports

All Python code lives under `backend/`, which acts as the **import root**: `main.py` imports `from agent.graph import graph`, agent modules import each other as `agent.tools` / `agent.utils`, and tools import `database.db_manager`. Keep this convention — do not import as `backend.xxx`. Entry points (`backend/main.py`, `backend/setup_database.py`) are run by path, so `backend/` lands on `sys.path` automatically.

File paths are anchored to `Path(__file__)` (`backend/database/config.py`, `backend/main.py`), never to the current working directory. Commands are still run from the repo root because `.env` lives there and `load_dotenv()` searches the cwd.

### LangGraph graph (`backend/agent/graph.py`)

`State` = `{messages: Annotated[list[AnyMessage], add_messages], user_info: str}`.

- Nodes: `assistant` → conditional edge `route_tools` → `safe_tools` or `sensitive_tools` → back to `assistant`. All tool nodes use `create_tool_node_with_fallback` from `utils.py`, which wraps `ToolNode` so exceptions become a `ToolMessage` ("Error: ... please fix your mistakes.") instead of crashing the graph.
- Compiled with `MemorySaver` checkpointer and `interrupt_before=["sensitive_tools"]`. The interrupt is the entire HITL mechanism: the graph pauses before running a sensitive tool and resumes via `graph.invoke(None, config)`.
- Conversation state is per-session, keyed on `configurable.thread_id` in the runtime config. The config shape everywhere is `{"configurable": {"customer_id": str, "thread_id": str}}` — `customer_id` is threaded into `State.user_info` by the `Assistant` node and read by tools.
- The `Assistant` node re-prompts ("Respond with a real output.") if the LLM returns an empty response.

### Tools (`backend/agent/tools.py`)

Five `@tool`-decorated functions, split in `graph.py`:

- **Safe (run immediately):** `get_available_categories`, `search_products`, `search_products_recommendations`, `check_order_status`
- **Sensitive (interrupted for approval):** `create_order`

Tools that need customer context declare `*, config: RunnableConfig` — LangGraph injects the runtime config automatically. All DB access goes through `DatabaseManager` (`backend/database/db_manager.py`) with the `sqlite3.Row` row factory, so queries return columns accessible by name. `create_order` wraps its inserts in an explicit transaction with rollback on error and decrements product `Quantity`.

### Streamlit frontend (`backend/main.py`)

Session state holds `messages`, a per-session `thread_id` (uuid4), and `config` with `customer_id` **hardcoded to `"123456789"`**.

HITL flow:
1. Chat calls `graph.stream({"messages": ...}, config, stream_mode="values")`.
2. If the last event's final message has `tool_calls`, it calls `graph.get_state(config)`; a non-empty `snapshot.next` means the graph interrupted before `sensitive_tools`.
3. Approval UI renders the proposed tool call. **Approve** = `graph.invoke(None, config)` (resume from interrupt). **Deny** = `graph.invoke` with a `ToolMessage` whose `tool_call_id` matches the pending call and content explains the denial.
4. "Start New Chat" clears all session state and reruns.

### Database layer (`backend/database/`, `backend/db/`)

- MySQL (local service `MySQL97`, MySQL 9.7) accessed via SQLAlchemy Core (`mysql+pymysql://`); database name defaults to `store` (utf8mb4).
- `backend/database/config.py`: `DatabaseConfig` dataclass; `get_config()` loads the repo-root `.env` itself and reads `MYSQL_HOST/PORT/USER/PASSWORD/DB`, **raising a clear error if `MYSQL_PASSWORD` is missing** — credentials are never hardcoded. Also pins schema/seed paths (`backend/db/schemas.sql`, `backend/db/products.json`, anchored to `Path(__file__)`). Change paths here, not in callers.
- `backend/database/db_manager.py`: `DatabaseManager` with two context managers — `get_connection()` for reads, `transaction()` (`engine.begin()`, commit on success / rollback on error) for writes. `create_database()` does `CREATE DATABASE IF NOT EXISTS` + executes the schema (statements split on `;`). `insert_products_from_json` loads via pandas and **lowercases** `product_name`/`category` (keys: `product_name`, `category`, `description`, `price`, `quantity`).
- `backend/setup_database.py`: creates DB + schema, seeds demo customer `123456789` (matches the hardcoded `customer_id` in `main.py`), seeds products only when the table is empty (idempotent).
- `backend/db/schemas.sql`: MySQL dialect (`AUTO_INCREMENT`, CHECK constraints — enforced on MySQL ≥ 8.0.16); creates `customers` (fixes the old dangling FK).

## Gotchas

- **Env var mismatch:** `graph.py` reads `os.getenv("PROJECT_ID")`, but `env-example` defines `GCP_PROJECT_ID`. Either set `PROJECT_ID` in `.env` or fix the code.
- `route_tools` and the approval UI in `main.py` both assume a **single tool call** per AI message (they only look at `tool_calls[0]`); parallel tool calls are not handled.
- `.gitignore` ignores `*.db` and `*.json`; `backend/db/products.json` is tracked only because it predates the rule — new JSON data files would be silently ignored.
- Tools run raw SQL through SQLAlchemy `text()` with `:named` params; rows must be fetched via `.mappings()` — bare `text()` rows are positional-only and string indexing raises `TypeError`.
- MySQL runs with `ONLY_FULL_GROUP_BY`: every `GROUP BY` query must list all selected non-aggregated columns (see `check_order_status`).
- MySQL FKs **are enforced** (unlike the old SQLite setup): `create_order` will fail if the customer doesn't exist in `customers` (seeded by `setup_database.py`).
- `main.py`'s approval flow re-runs the whole Streamlit script per interaction; session state (including `pending_approval`) is the only persistence between reruns.
