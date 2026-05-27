import json
from asyncio import sleep
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import Settings

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


def _dereference_schema(schema: dict) -> dict:
    """Recursively inline $defs references in JSON schema to make it readable for smaller LLMs."""
    def resolve(node, defs):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_path = node["$ref"]
                if ref_path.startswith("#/$defs/"):
                    def_name = ref_path.split("/")[-1]
                    ref_node = defs.get(def_name, {})
                    return resolve(ref_node, defs)
            return {k: resolve(v, defs) for k, v in node.items()}
        elif isinstance(node, list):
            return [resolve(item, defs) for item in node]
        return node

    defs = schema.get("$defs", {})
    resolved = resolve(schema, defs)
    if "$defs" in resolved:
        del resolved["$defs"]
    return resolved


class GroqLLMProvider:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.groq_api_key
        self._model = settings.groq_model
        self._fallback_models = [
            model.strip()
            for model in settings.groq_fallback_models.split(",")
            if model.strip() and model.strip() != self._model
        ]
        self._timeout = settings.groq_timeout_seconds
        self._base_url = settings.groq_base_url.rstrip("/")
        self._max_retries = max(0, settings.groq_max_retries)
        self._retry_base_delay_seconds = max(0.1, settings.groq_retry_base_delay_seconds)
        self._temperature = settings.groq_temperature
        self._gemini_api_key = settings.gemini_api_key
        self._gemini_model = settings.gemini_model
        self._gemini_base_url = settings.gemini_base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._misconfigured_error: str | None = None

    async def structured_completion(
        self,
        *,
        instructions: str,
        user_prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredModel:
        # Generate the JSON schema from the response_model Pydantic model to guide the LLM precisely
        try:
            schema_dict = response_model.model_json_schema()
            derefed_schema = _dereference_schema(schema_dict)
            schema_json = json.dumps(derefed_schema, indent=2)
            schema_instructions = (
                f"{instructions}\n\n"
                f"You MUST return a JSON object that strictly adheres to the following JSON Schema:\n"
                f"{schema_json}\n\n"
                f"Ensure every list field is a JSON array (not a nested object), "
                f"and all fields match their schema names and types exactly."
            )
        except Exception as err:
            print(f"[WARN] Failed to generate JSON schema: {err}")
            schema_instructions = instructions

        payload = await self.json_completion(
            instructions=schema_instructions,
            user_prompt=user_prompt,
        )
        return response_model.model_validate(payload)

    async def json_completion(
        self,
        *,
        instructions: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        if self._misconfigured_error:
            raise RuntimeError(self._misconfigured_error)
        if not self._api_key and not self._gemini_api_key:
            self._misconfigured_error = "Neither GROQ_API_KEY nor GEMINI_API_KEY is configured."
            raise ValueError(self._misconfigured_error)

        errors: list[str] = []
        models = [self._model, *self._fallback_models]

        for model_name in models:
            if not self._api_key:
                break
            try:
                return await self._structured_completion_with_model(
                    model_name=model_name,
                    instructions=instructions,
                    user_prompt=user_prompt,
                )
            except RuntimeError as exc:
                errors.append(f"{model_name}: {exc}")

        if self._gemini_api_key:
            try:
                return await self._structured_completion_with_gemini(
                    instructions=instructions,
                    user_prompt=user_prompt,
                )
            except RuntimeError as exc:
                errors.append(f"gemini ({self._gemini_model}): {exc}")

        raise RuntimeError(" | ".join(errors))

    async def _structured_completion_with_model(
        self,
        *,
        model_name: str,
        instructions: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        client = self._get_client()

        for attempt in range(self._max_retries + 1):
            try:
                response = await client.post(
                    "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    f"{instructions}\n\n"
                                    "Return only valid JSON matching the requested schema. "
                                    "Prefer the schema's exact field names and enum values. "
                                    "Do not include markdown fences or explanatory text."
                                ),
                            },
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": self._temperature,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                detail = exc.response.text[:500]
                if status_code == 429 and attempt < self._max_retries:
                    await sleep(self._retry_delay_seconds(attempt))
                    continue
                raise RuntimeError(f"Groq API error {status_code}: {detail}") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await sleep(self._retry_delay_seconds(attempt))
                    continue
                raise RuntimeError(f"Groq connection error: {exc}") from exc

            body = response.json()
            try:
                content = body["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Groq returned an unexpected response payload: {body}") from exc

            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Groq returned no structured result.")

            try:
                payload = self._parse_json_payload(content)
            except json.JSONDecodeError as exc:
                preview = content[:500]
                raise RuntimeError(f"Groq returned invalid JSON: {preview}") from exc

            if isinstance(payload, list):
                payload = {"items": payload}

            if not isinstance(payload, dict):
                raise RuntimeError("Groq returned JSON, but not an object payload.")
            return payload

        raise RuntimeError(f"Groq request exhausted retries for model {model_name}.")

    async def _structured_completion_with_gemini(
        self,
        *,
        instructions: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        client = self._get_client()
        url = f"{self._gemini_base_url}/{self._gemini_model}:generateContent"

        for attempt in range(self._max_retries + 1):
            try:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    params={"key": self._gemini_api_key},
                    json={
                        "system_instruction": {
                            "parts": [{"text": (
                                f"{instructions}\n\n"
                                "Return only valid JSON matching the requested schema. "
                                "Prefer the schema's exact field names and enum values. "
                                "Do not include markdown fences or explanatory text."
                            )}]
                        },
                        "contents": [{
                            "parts": [{"text": user_prompt}]
                        }],
                        "generationConfig": {
                            "temperature": self._temperature,
                            "response_mime_type": "application/json"
                        }
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                detail = exc.response.text[:500]
                if status_code == 429 and attempt < self._max_retries:
                    await sleep(self._retry_delay_seconds(attempt))
                    continue
                raise RuntimeError(f"Gemini API error {status_code}: {detail}") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await sleep(self._retry_delay_seconds(attempt))
                    continue
                raise RuntimeError(f"Gemini connection error: {exc}") from exc

            body = response.json()
            try:
                content = body["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Gemini returned an unexpected response payload: {body}") from exc

            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Gemini returned no structured result.")

            try:
                payload = self._parse_json_payload(content)
            except json.JSONDecodeError as exc:
                preview = content[:500]
                raise RuntimeError(f"Gemini returned invalid JSON: {preview}") from exc

            if isinstance(payload, list):
                payload = {"items": payload}

            if not isinstance(payload, dict):
                raise RuntimeError("Gemini returned JSON, but not an object payload.")
            return payload

        raise RuntimeError(f"Gemini request exhausted retries for model {self._gemini_model}.")

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                limits=limits,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None

    def _retry_delay_seconds(self, attempt: int) -> float:
        return self._retry_base_delay_seconds * (2**attempt)

    @staticmethod
    def _parse_json_payload(content: str) -> dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            stripped = content.strip()
            if stripped.startswith("```"):
                stripped = stripped.strip("`")
                if stripped.lower().startswith("json"):
                    stripped = stripped[4:].strip()
            start_positions = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
            if not start_positions:
                raise
            start = min(start_positions)
            end_object = stripped.rfind("}")
            end_array = stripped.rfind("]")
            end = max(end_object, end_array)
            if end < start:
                raise
            payload = json.loads(stripped[start : end + 1])

        if isinstance(payload, list):
            payload = {"items": payload}

        if not isinstance(payload, dict):
            raise json.JSONDecodeError("JSON payload was not an object", content, 0)
        return payload
