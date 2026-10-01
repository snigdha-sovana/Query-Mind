"""Thin LLM wrapper. Unit tests inject a callable instead of this client."""

from __future__ import annotations

import time
from typing import Any, Callable

from querymind.config import (
    GEMINI_API_KEY,
    GROK_API_KEY,
    GROQ_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OPENAI_API_KEY,
)


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item and isinstance(item["text"], str):
                    parts.append(item["text"])
                elif "content" in item:
                    parts.append(_extract_text(item["content"]))
        if parts:
            return "\n".join(parts)
    return str(content)


FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-1.5-flash"]


class LLMClient:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        max_retries: int = 4,
    ):
        self.provider = (provider or LLM_PROVIDER).lower()
        self.model = model or LLM_MODEL
        if api_key is not None:
            self.api_key = api_key
        elif self.provider in {"grok", "xai"}:
            self.api_key = GROK_API_KEY
        elif self.provider in {"groq"}:
            self.api_key = GROQ_API_KEY
        elif self.provider in {"openai"}:
            self.api_key = OPENAI_API_KEY
        else:
            self.api_key = GEMINI_API_KEY
        self.max_retries = max_retries
        self._active_model = self.model
        self._invoke = self._build_invoke(self._active_model)

    def _build_invoke(self, model_name: str) -> Callable[[str], str]:
        if self.provider in {"gemini", "google"}:
            if not self.api_key or self.api_key == "your_gemini_api_key_here":
                raise RuntimeError(
                    "GEMINI_API_KEY is not set. Put it in .env or pass api_key=..."
                )
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=self.api_key)

            def _call(prompt: str) -> str:
                response = llm.invoke(prompt)
                content = getattr(response, "content", response)
                return _extract_text(content)

            return _call

        if self.provider in {"grok", "xai"}:
            if not self.api_key:
                raise RuntimeError("GROK_API_KEY or XAI_API_KEY is not set. Put it in .env or pass api_key=...")
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=model_name or "grok-2-latest",
                api_key=self.api_key,
                base_url="https://api.x.ai/v1",
            )

            def _call_grok(prompt: str) -> str:
                response = llm.invoke(prompt)
                content = getattr(response, "content", response)
                return _extract_text(content)

            return _call_grok

        if self.provider in {"ollama"}:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=model_name or "qwen2.5-coder",
                api_key="ollama",
                base_url=OLLAMA_BASE_URL,
            )

            def _call_ollama(prompt: str) -> str:
                response = llm.invoke(prompt)
                content = getattr(response, "content", response)
                return _extract_text(content)

            return _call_ollama

        if self.provider in {"groq"}:
            if not self.api_key:
                raise RuntimeError("GROQ_API_KEY is not set. Put it in .env or pass api_key=...")
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=model_name or "qwen/qwen3.8-27b",
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1",
            )

            def _call_groq(prompt: str) -> str:
                response = llm.invoke(prompt)
                content = getattr(response, "content", response)
                return _extract_text(content)

            return _call_groq

        if self.provider in {"openai"}:
            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is not set. Put it in .env or pass api_key=...")
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(model=model_name or "gpt-4o-mini", api_key=self.api_key)

            def _call_openai(prompt: str) -> str:
                response = llm.invoke(prompt)
                content = getattr(response, "content", response)
                return _extract_text(content)

            return _call_openai

        raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def __call__(self, prompt: str) -> str:
        import hashlib
        import sqlite3
        from pathlib import Path

        cache_path = Path(".llm_cache.sqlite")
        try:
            conn = sqlite3.connect(cache_path)
            conn.execute("CREATE TABLE IF NOT EXISTS cache (hash TEXT PRIMARY KEY, response TEXT)")
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            cursor = conn.execute("SELECT response FROM cache WHERE hash = ?", (prompt_hash,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row[0]
        except Exception:
            pass

        delay = 2.0
        max_delay = 30.0
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                result = self._invoke(prompt)
                try:
                    conn = sqlite3.connect(cache_path)
                    conn.execute("INSERT OR REPLACE INTO cache (hash, response) VALUES (?, ?)", (prompt_hash, result))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
                return result
            except Exception as exc:  # noqa: BLE001 — retry on provider errors
                last_error = exc
                if _should_fallback_or_retry(exc):
                    provider = getattr(self, "provider", "")
                    if provider in {"gemini", "google"}:
                        # Attempt fallback to alternative available Gemini models
                        active_model = getattr(self, "_active_model", None)
                        for fb in FALLBACK_MODELS:
                            if fb != active_model:
                                try:
                                    fb_invoker = self._build_invoke(fb)
                                    result = fb_invoker(prompt)
                                    self._active_model = fb
                                    self._invoke = fb_invoker
                                    try:
                                        conn = sqlite3.connect(cache_path)
                                        conn.execute("INSERT OR REPLACE INTO cache (hash, response) VALUES (?, ?)", (prompt_hash, result))
                                        conn.commit()
                                        conn.close()
                                    except Exception:
                                        pass
                                    return result
                                except Exception:
                                    continue
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
                else:
                    raise
        raise last_error or RuntimeError("LLM call failed")


def _should_fallback_or_retry(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(pattern in text for pattern in ["429", "resource exhausted", "rate limit", "404", "not found", "no longer available"])


def get_llm_caller() -> Callable[[str], str]:
    return LLMClient()

