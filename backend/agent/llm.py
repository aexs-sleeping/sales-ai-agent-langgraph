"""LLM provider factory — config-driven.

The agent only depends on the OpenAI-compatible langchain chat-model
interface, so any provider is interchangeable from the agent's perspective.
Supported providers (set via `LLM_PROVIDER`):
  - deepseek: DeepSeek-V4-Flash over the OpenAI-compatible API
    (requires DEEPSEEK_API_KEY)
  - gemini:  Google Vertex AI Gemini Flash (default; requires
    GCP_PROJECT_ID and REGION)
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """Build the chat model selected by the LLM_PROVIDER env var."""
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "LLM_PROVIDER=deepseek requires DEEPSEEK_API_KEY. "
                "Copy env-example to .env and fill in the key."
            )
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="deepseek-v4-flash",
            api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=0,
        )

    if provider == "gemini":
        from google.cloud import aiplatform
        from langchain_google_vertexai import ChatVertexAI

        # Read GCP_PROJECT_ID (the env-example key) with PROJECT_ID as fallback —
        # fixes the historical mismatch where the code only read PROJECT_ID.
        project = os.getenv("GCP_PROJECT_ID") or os.getenv("PROJECT_ID")
        region = os.getenv("REGION")
        if not project or not region:
            raise ValueError(
                "LLM_PROVIDER=gemini requires GCP_PROJECT_ID (or PROJECT_ID) and REGION. "
                "Set them in .env, or switch to LLM_PROVIDER=deepseek."
            )
        aiplatform.init(project=project, location=region)
        return ChatVertexAI(model="gemini-2.0-flash-exp")

    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Supported: gemini, deepseek.")
