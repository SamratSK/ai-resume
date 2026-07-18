"""Single HTTP client class behind which both model roles (extraction and
interpretation) sit. Every endpoint the pipeline talks to is an instance of
this class, configured from config.yaml — no role-specific behavior here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from resume_pipeline.config import ModelEndpointConfig


class LLMClient:
    def __init__(self, endpoint: ModelEndpointConfig):
        self.endpoint = endpoint
        self._http = httpx.Client(base_url=endpoint.base_url, timeout=endpoint.timeout_seconds)

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        response_format_json: bool = False,
        temperature: Optional[float] = None,
    ) -> str:
        """POST /chat/completions (OpenAI-compatible), return the assistant's
        raw text content. Raises httpx.HTTPError on transport/HTTP failure —
        callers decide how to handle that (retry, mark Failed, etc.)."""
        payload: Dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": messages,
            "temperature": self.endpoint.temperature if temperature is None else temperature,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        response = self._http.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
