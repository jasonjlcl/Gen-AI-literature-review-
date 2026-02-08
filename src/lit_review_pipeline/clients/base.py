"""Base interface for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Abstract LLM client contract."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider identifier."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text output for a prompt."""
