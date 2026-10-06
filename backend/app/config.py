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
    # The Activity Monitor judges the writing process from the whole context
    # (draft, conversation, notes). A lite model keeps the extra call cheap;
    # point this at a full flash model for sharper judgements at more latency.
    gemini_monitor_model: str = "gemini-flash-lite-latest"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    default_provider: str = "gemini"
    database_url: str = "sqlite:///./storystudio.db"

    # Comma-separated origins the browser is allowed to call this API from.
    # The frontend normally reaches the backend through its own rewrite proxy
    # (next.config.ts -> BACKEND_URL), so the browser's origin is itself, not
    # the backend's - these defaults cover that local-dev case. Deployed
    # somewhere real, set this to the frontend's public URL as a second layer
    # of defence (e.g. for anyone hitting the backend's /docs directly).
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

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

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
