from __future__ import annotations

import os

# Set test environment variables BEFORE any app module is imported,
# so the Settings singleton is constructed with mock_llm=True.
os.environ["MOCK_LLM"] = "true"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8001")
