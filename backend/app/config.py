"""Runtime settings. Everything the researcher can flip lives here or in PromptConfig."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    # Tried in order when the primary model returns 429/404. Free-tier daily
    # quotas are per-model, so a sibling is usually still available.
    gemini_fallback_models: str = "gemini-3.6-flash,gemini-3-flash-preview,gemini-flash-lite-latest"
    # Intent classification is a one-word task; a lite model halves the
    # round trip and keeps the turn inside the HLD 11.1 latency budget.
    gemini_classifier_model: str = "gemini-flash-lite-latest"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    default_provider: str = "gemini"
    database_url: str = "sqlite:///./storystudio.db"


    @property
    def effective_provider(self) -> str:
        """Never boot into a provider that cannot answer.

        A demo that shows an error on first use is worse than one that runs on
        the offline scaffold, so an unset key silently downgrades rather than
        failing. The researcher panel still shows exactly what is active.
        """
        if self.default_provider == "gemini" and not self.gemini_api_key:
            return "echo"
        return self.default_provider


settings = Settings()
