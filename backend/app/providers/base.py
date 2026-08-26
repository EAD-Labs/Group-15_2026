"""Provider abstraction - HLD 6.1 Module 3 "Multi-LLM Router".

One interface, several backends, swappable at runtime without a restart (UC-03).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMReply:
    text: str
    model: str
    provider: str


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(
        self, system: str, user: str, temperature: float = 0.8, max_tokens: int = 600
    ) -> LLMReply:
        """Single-shot completion."""

    @abstractmethod
    async def health(self) -> tuple[bool, str]:
        """(reachable, human-readable status)."""
