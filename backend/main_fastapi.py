"""FastAPI backend entry point for the virtual sales agent (PRD §3).

Run from the repository root:

    uvicorn backend.main_fastapi:app --port 8000

or directly:

    python backend/main_fastapi.py          # port from PORT / API_PORT, default 8000

The agent graph is imported lazily inside the chat handlers, so this module and
`/api/health` + `/api/conversations` work without Google credentials.
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Anchor `backend/` on sys.path so `api.*`, `agent.*` and `database.*` imports
# resolve regardless of how uvicorn launches the module.
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from api.chat import router as chat_router  # noqa: E402
from api.conversations import router as conversations_router  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Virtual Sales Agent API", version="1.0.0")

# Vite dev servers (PRD §3.4).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations_router)
app.include_router(chat_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT") or os.getenv("PORT") or "8000")
    logger.info("Starting Virtual Sales Agent API on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
