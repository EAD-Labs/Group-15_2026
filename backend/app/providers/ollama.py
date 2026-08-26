"""Local models through Ollama - the offline / sSLM path from HLD 7.1."""
import httpx

from .base import LLMProvider, LLMReply


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, system, user, temperature=0.8, max_tokens=600) -> LLMReply:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            # Without this the model is evicted between turns and every request
            # pays a ~45s reload. Holding it resident is the difference between
            # a usable local demo and an unusable one.
            "keep_alive": "30m",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{self.base_url}/api/chat", json=body)
            if r.status_code != 200:
                raise RuntimeError(f"Ollama {r.status_code}: {r.text[:300]}")
            data = r.json()
        return LLMReply(
            text=data.get("message", {}).get("content", "").strip(),
            model=self.model,
            provider=self.name,
        )

    async def health(self):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}"
            names = [m["name"] for m in r.json().get("models", [])]
            if not names:
                return False, "Running, but no models pulled"
            if not any(n.split(":")[0] == self.model.split(":")[0] for n in names):
                return False, f"{self.model} not pulled ({len(names)} other model(s) available)"
            return True, f"Ready ({self.model})"
        except Exception:
            return False, "Not running - try `ollama serve`"
