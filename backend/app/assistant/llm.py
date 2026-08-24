import httpx

from app.core.config import get_settings


class OllamaLLMClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        settings = get_settings()

        self.base_url = (
            base_url or settings.ollama_base_url
        ).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
    ) -> str:
        prompt = prompt.strip()

        if not prompt:
            raise ValueError("prompt cannot be empty")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = data.get("response")

        if not isinstance(text, str):
            raise ValueError(
                "Ollama response did not contain generated text"
            )

        return text.strip()
