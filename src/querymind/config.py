"""Runtime configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or raw == "" else int(raw)


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or raw == "" else float(raw)


def _get_val(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


GEMINI_API_KEY = _get_val("GEMINI_API_KEY", "")
GROK_API_KEY = _get_val("GROK_API_KEY", _get_val("XAI_API_KEY", ""))
OPENAI_API_KEY = _get_val("OPENAI_API_KEY", "")
GROQ_API_KEY = _get_val("GROQ_API_KEY", "")
OLLAMA_BASE_URL = _get_val("OLLAMA_BASE_URL", "http://localhost:11434/v1")

LLM_MODEL = _get_val("QUERYMIND_LLM_MODEL", "qwen/qwen3.8-27b")
LLM_PROVIDER = _get_val("QUERYMIND_LLM_PROVIDER", "groq")

DATA_DIR = Path(os.getenv("QUERYMIND_DATA_DIR", str(ROOT / "data" / "bird_mini_dev")))
ROW_LIMIT = _int("QUERYMIND_ROW_LIMIT", 500)
QUERY_TIMEOUT_S = _float("QUERYMIND_QUERY_TIMEOUT_S", 10.0)
MAX_SQL_RETRIES = _int("QUERYMIND_MAX_SQL_RETRIES", 3)
SCHEMA_TOP_K = _int("QUERYMIND_SCHEMA_TOP_K", 6)
MAX_INVESTIGATION_ITERS = _int("QUERYMIND_MAX_ITERS", 3)

# Bundled Mini-Dev copy (local checkout). Not used by unit tests.
BUNDLED_MINIDEV = ROOT / "minidev docs" / "minidev" / "MINIDEV"
