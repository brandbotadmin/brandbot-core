import json
import re
import httpx
from config.settings import settings


class AIContextAnalyzer:
    @staticmethod
    async def analyze_market_context(headlines: list[str], client: httpx.AsyncClient | None = None) -> dict:
        if not settings.OLLAMA_ENABLED:
            return {"context_score": 100, "reason": "LLM disabled", "source": "skipped"}

        prompt = (
            "Return ONLY JSON like {\"context_score\": 0-100, \"reason\": \"...\"} "
            f"for trading risk given headlines: {headlines}"
        )
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=3.0) as local_client:
                    res = await local_client.post(
                        f"{settings.OLLAMA_HOST}/api/generate",
                        json={"model": "llama3", "prompt": prompt, "stream": False},
                    )
            else:
                res = await client.post(
                    f"{settings.OLLAMA_HOST}/api/generate",
                    json={"model": "llama3", "prompt": prompt, "stream": False},
                    timeout=3.0,
                )
            if res.status_code != 200:
                return {"context_score": 100, "reason": "LLM unavailable", "source": "fallback"}
            body = res.json()
            text = body.get("response", "")
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                score = int(parsed.get("context_score", 100))
                return {
                    "context_score": max(0, min(100, score)),
                    "reason": str(parsed.get("reason", "OK")),
                    "source": "ollama",
                }
        except Exception:
            pass
        return {"context_score": 100, "reason": "LLM parse fallback", "source": "fallback"}
