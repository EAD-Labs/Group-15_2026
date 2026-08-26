"""Google Gemini via the REST API. No SDK dependency."""
import httpx

from .base import LLMProvider, LLMReply

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


class _QuotaExhausted(Exception):
    """This model is unavailable (rate-limited or retired); try the next one."""


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, fallbacks: tuple[str, ...] = ()):
        self.api_key = api_key
        self.model = model
        # Gemini free-tier quotas are per-model and small (gemini-3.6-flash is
        # 20 requests/day). Rather than dropping a live demo to the offline
        # scaffold the moment one model is exhausted, walk a chain of siblings
        # first - a different model is a far better degradation than no model.
        self.fallbacks = tuple(m for m in fallbacks if m and m != model)

    async def complete(self, system, user, temperature=0.8, max_tokens=600) -> LLMReply:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to backend/.env")

        last_error = ""
        for model in (self.model, *self.fallbacks):
            try:
                return await self._call(model, system, user, temperature, max_tokens)
            except _QuotaExhausted as exc:
                last_error = str(exc)
                continue
        raise RuntimeError(last_error or "All Gemini models exhausted")

    async def _call(self, model, system, user, temperature, max_tokens) -> LLMReply:
        gen: dict = {"temperature": temperature, "maxOutputTokens": max_tokens}

        # Gemini 3.x reasons before answering. Left unbounded that burns the
        # output budget (truncating replies mid-sentence) and adds seconds of
        # latency, which HLD 11.1 budgets at under 4s. Socratic questioning is
        # a shallow task, so we ask for minimal deliberation.
        if model.startswith("gemini-3"):
            gen["thinkingConfig"] = {"thinkingLevel": "LOW"}

        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen,
        }
        url = f"{API_ROOT}/{model}:generateContent"
        headers = {"x-goog-api-key": self.api_key}

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=body, headers=headers)
            # Older models reject thinkingConfig outright - drop it and retry.
            if r.status_code == 400 and "thinking" in r.text.lower():
                gen.pop("thinkingConfig", None)
                r = await client.post(url, json=body, headers=headers)
            if r.status_code in (429, 404):
                raise _QuotaExhausted(f"{model}: HTTP {r.status_code}")
            if r.status_code != 200:
                raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
            data = r.json()

        try:
            parts = data["candidates"][0]["content"]["parts"]
            # Skip reasoning parts - only the visible answer belongs to the student.
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (KeyError, IndexError):
            # Safety block or empty candidate.
            reason = data.get("candidates", [{}])[0].get("finishReason", "unknown")
            raise RuntimeError(f"Gemini returned no text (finishReason={reason})")

        return LLMReply(text=text.strip(), model=model, provider=self.name)

    async def health(self):
        if not self.api_key:
            return False, "No API key set"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{API_ROOT}/{self.model}", headers={"x-goog-api-key": self.api_key}
                )
            if r.status_code == 200:
                return True, f"Ready ({self.model})"
            return False, f"HTTP {r.status_code}"
        except Exception as exc:
            return False, str(exc)[:80]
