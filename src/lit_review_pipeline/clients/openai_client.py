"""OpenAI LLM client implementation."""

from __future__ import annotations

import requests

from ..config import Settings
from .base import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """OpenAI chat completions API client."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self._api_key = settings.openai_api_key
        self._model = settings.openai_model
        self._timeout = settings.llm_request_timeout_seconds
        self._temperature = settings.llm_temperature

    @property
    def provider(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise extraction engine that returns valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenAI response contained no choices.")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if not content:
            raise ValueError("OpenAI response content was empty.")
        return content.strip()
