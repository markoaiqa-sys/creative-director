import base64
import httpx
from typing import List

from app.core.config import Settings


class ImageAnalyzer:
    """Analyze images and return a short textual description.

    Preference order:
    1. If `groq_vision_endpoint` and `groq_api_key` are configured, POST there.
    2. Use HuggingFace image captioning model (configured by `hf_image_caption_model`).
    3. Otherwise return empty string.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(timeout=60.0)
        self._hf_caption_model = settings.hf_image_caption_model  # For image analysis/captioning
        # Optional user-provided groq vision endpoint (not present by default)
        self._grok_vision_endpoint = getattr(settings, "groq_vision_endpoint", None)
        self._grok_api_key = settings.groq_api_key

    async def describe_images(self, sample_images: List[str]) -> str:
        if not sample_images:
            return ""

        # Try Groq vision endpoint if configured
        from app.providers.groq_llm import custom_groq_key_var
        custom_key = custom_groq_key_var.get()
        api_key = custom_key if custom_key else self._grok_api_key

        if self._grok_vision_endpoint and api_key:
            try:
                # send base64 images as JSON
                imgs = []
                for img in sample_images:
                    if img.startswith("data:"):
                        imgs.append(img.split(",", 1)[1])
                    else:
                        imgs.append(img)
                payload = {"images": imgs}
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                res = await self._client.post(self._grok_vision_endpoint, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    # Expecting {'description': '...'} or similar
                    if isinstance(data, dict):
                        return data.get("description", "").strip()
                    return str(data)[:400]
                else:
                    print(f"[WARN] Groq vision endpoint returned {res.status_code}: {res.text[:400]}")
            except Exception as e:
                print(f"[WARN] Groq vision call failed: {e}")

        # Fall back to Hugging Face image-captioning model
        if self._settings.hf_api_key and self._hf_caption_model:
            try:
                url = f"https://api-inference.huggingface.co/models/{self._hf_caption_model}"
                headers = {"Authorization": f"Bearer {self._settings.hf_api_key}"}
                # send first image binary
                img = sample_images[0]
                if img.startswith("data:"):
                    b64 = img.split(",", 1)[1]
                    img_bytes = base64.b64decode(b64)
                else:
                    # assume raw base64
                    img_bytes = base64.b64decode(img)

                res = await self._client.post(url, headers=headers, content=img_bytes)
                if res.status_code == 200:
                    # HF captioning models return JSON list with generated_text or dict
                    try:
                        body = res.json()
                        if isinstance(body, list) and len(body) > 0:
                            # Common format: [{"generated_text": "..."}, ...]
                            first = body[0]
                            if isinstance(first, dict):
                                for k in ("generated_text", "caption", "text"):
                                    if k in first and isinstance(first[k], str):
                                        return first[k].strip()
                        if isinstance(body, dict):
                            # try common keys
                            for k in ("generated_text", "caption", "text"):
                                if k in body and isinstance(body[k], str):
                                    return body[k].strip()
                            # fallback to first value
                            for v in body.values():
                                if isinstance(v, str) and v.strip():
                                    return v.strip()
                            return str(body)[:400]
                    except Exception:
                        # not json — treat as plain text
                        text = res.text.strip()
                        if text:
                            return text
                else:
                    print(f"[WARN] HF caption model returned {res.status_code}: {res.text[:400]}")
            except Exception as e:
                print(f"[WARN] HuggingFace image caption failed: {e}")

        return ""

    async def aclose(self) -> None:
        await self._client.aclose()
