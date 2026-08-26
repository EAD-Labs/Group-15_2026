"""Provider registry - the runtime-swappable router (UC-03)."""
from ..config import settings
from .base import LLMProvider, LLMReply
from .echo import EchoProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider

__all__ = ["LLMProvider", "LLMReply", "get_provider", "available_providers"]


def get_provider(name: str, model_override: str = "") -> LLMProvider:
    name = (name or settings.effective_provider).lower()
    if name == "gemini":
        return GeminiProvider(
            settings.gemini_api_key,
            model_override or settings.gemini_model,
            tuple(m.strip() for m in settings.gemini_fallback_models.split(",") if m.strip()),
        )
    if name == "ollama":
        return OllamaProvider(settings.ollama_base_url, model_override or settings.ollama_model)
    return EchoProvider()


def available_providers() -> list[dict]:
    return [
        {"id": "gemini", "label": "Google Gemini", "model": settings.gemini_model,
         "hint": "Cloud API - best instruction-following"},
        {"id": "ollama", "label": "Ollama (local)", "model": settings.ollama_model,
         "hint": "Runs on this machine, fully offline"},
        {"id": "echo", "label": "Offline Scaffold", "model": "offline-socratic-v1",
         "hint": "Deterministic, no model required"},
    ]
