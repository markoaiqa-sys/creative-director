import asyncio
import base64
import binascii
import io
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.core.config import Settings
from app.models import CreativeStatus, GeneratedCreative, Platform, VisualConcept

ImageGenerationModel = None
VertexImage = None
aiplatform = None
genai = None
VERTEX_AI_AVAILABLE = False
VERTEX_AI_IMPORT_ERROR = None

try:
    from vertexai.preview.vision_models import Image as VertexImage
    from vertexai.preview.vision_models import ImageGenerationModel
    from google.cloud import aiplatform

    VERTEX_AI_AVAILABLE = True
except ImportError as e:
    try:
        # Fallback path for older/newer SDK layout changes.
        from vertexai.vision_models import Image as VertexImage
        from vertexai.vision_models import ImageGenerationModel
        from google.cloud import aiplatform

        VERTEX_AI_AVAILABLE = True
    except ImportError as e2:
        VERTEX_AI_IMPORT_ERROR = f"{e}; fallback failed: {e2}"
        print(f"[VERTEX_AI] Import failed: {VERTEX_AI_IMPORT_ERROR}")

try:
    from google import genai
except ImportError:
    genai = None


class VertexAIClient:
    _TARGET_SIZES: dict[str, tuple[int, int]] = {
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "9:16": (1080, 1920),
        "16:9": (1200, 675),
        "1.91:1": (1200, 628),
    }

    def __init__(self, settings: Settings) -> None:
        self._project_id = settings.vertex_ai_project_id
        self._location = settings.vertex_ai_location
        self._provider = (settings.vertex_ai_provider or "imagen").strip().lower()
        self._model_name = settings.vertex_ai_image_model
        self._edit_model_name = "imagen-3.0-capability-001"
        self._client = None
        self._edit_client = None
        self._gemini_client = None

        if not self._project_id:
            print(
                "[VERTEX_AI] Skipped - "
                f"project_id={self._project_id}, "
                f"import_error={VERTEX_AI_IMPORT_ERROR}"
            )
            return

        if self._provider == "gemini_image":
            self._init_gemini_image_client()
            return

        self._init_imagen_client()

    def _init_imagen_client(self) -> None:
        if not VERTEX_AI_AVAILABLE:
            print(
                "[VERTEX_AI] Imagen unavailable - "
                f"VERTEX_AI_AVAILABLE={VERTEX_AI_AVAILABLE}, "
                f"import_error={VERTEX_AI_IMPORT_ERROR}"
            )
            return
        try:
            print(f"[VERTEX_AI] Initializing Imagen with project={self._project_id}, location={self._location}")
            aiplatform.init(project=self._project_id, location=self._location)
            self._client = ImageGenerationModel.from_pretrained(self._model_name)
            try:
                self._edit_client = ImageGenerationModel.from_pretrained(self._edit_model_name)
                print(f"[VERTEX_AI] Initialized edit model: {self._edit_model_name}")
            except Exception as edit_exc:
                print(f"[VERTEX_AI] Edit model init failed ({self._edit_model_name}): {edit_exc}")
                self._edit_client = None
            print("[VERTEX_AI] Initialized Vertex AI Imagen client")
        except Exception as e:
            print(f"[VERTEX_AI] Failed to initialize Imagen client: {type(e).__name__}: {e}")
            self._client = None
            self._edit_client = None

    def _init_gemini_image_client(self) -> None:
        if genai is None:
            print("[VERTEX_AI] Gemini image mode requested but `google-genai` is not installed.")
            return
        try:
            print(f"[VERTEX_AI] Initializing Gemini Image with project={self._project_id}, location={self._location}")
            self._gemini_client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._location,
            )
            print("[VERTEX_AI] Initialized Vertex AI Gemini image client")
        except Exception as e:
            print(f"[VERTEX_AI] Failed to initialize Gemini image client: {type(e).__name__}: {e}")
            self._gemini_client = None

    async def generate_batch(
        self,
        concepts: list[VisualConcept],
        *,
        platform: Platform,
        sample_images: list[str] | None = None,
    ) -> list[GeneratedCreative]:
        per_image_timeout = 180
        
        async def _generate_with_timeout(concept: VisualConcept) -> GeneratedCreative:
            try:
                return await asyncio.wait_for(
                    self.generate_creative(concept, platform=platform, sample_images=sample_images),
                    timeout=per_image_timeout,
                )
            except Exception as e:
                print(f"[VERTEX_AI] Image failed: {type(e).__name__}: {e}")
                return GeneratedCreative(
                    concept_id=concept.concept_id,
                    provider="vertex-ai",
                    status=CreativeStatus.FAILED,
                    prompt=concept.generation_prompt,
                    error=f"Per-image timeout/error: {type(e).__name__}: {e}",
                )

        tasks = [_generate_with_timeout(concept) for concept in concepts]
        return list(await asyncio.gather(*tasks))

    async def generate_creative(
        self,
        concept: VisualConcept,
        *,
        platform: Platform,
        sample_images: list[str] | None = None,
    ) -> GeneratedCreative:
        client_ready = bool(self._gemini_client) if self._provider == "gemini_image" else bool(self._client)
        if not self._project_id or not client_ready:
            return GeneratedCreative(
                concept_id=concept.concept_id,
                provider="vertex-ai",
                status=CreativeStatus.SKIPPED,
                prompt=concept.generation_prompt,
                error=(
                    "Vertex AI unavailable. Check VERTEX_AI_PROJECT_ID, credentials, "
                    "selected provider setup, and package compatibility."
                ),
            )

        max_attempts = 2
        last_error = ""
        for attempt in range(max_attempts):
            try:
                if self._provider == "gemini_image":
                    image_urls = await self._call_gemini_image_api(concept, sample_images=sample_images)
                else:
                    image_urls = await self._call_imagen_api(concept, sample_images=sample_images)
                if image_urls:
                    return GeneratedCreative(
                        concept_id=concept.concept_id,
                        provider="vertex-ai",
                        provider_api_version=self._model_name,
                        status=CreativeStatus.GENERATED,
                        prompt=concept.generation_prompt,
                        image_urls=image_urls,
                        video_urls=[],
                        raw_response={"urls": image_urls},
                    )
                last_error = "No usable image bytes in response"
                if attempt < max_attempts - 1:
                    print(f"[VERTEX_AI] {concept.concept_id} attempt {attempt+1}: no image bytes, retrying in 5s...")
                    await asyncio.sleep(5)
            except Exception as e:
                last_error = str(e)
                if attempt < max_attempts - 1:
                    print(f"[VERTEX_AI] {concept.concept_id} attempt {attempt+1} error: {e}, retrying in 5s...")
                    await asyncio.sleep(5)

        return GeneratedCreative(
            concept_id=concept.concept_id,
            provider="vertex-ai",
            status=CreativeStatus.FAILED,
            prompt=concept.generation_prompt,
            error=f"Failed after {max_attempts} attempts: {last_error}",
        )

    async def _call_gemini_image_api(self, concept: VisualConcept, sample_images: list[str] | None = None) -> list[str]:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._generate_gemini_image_sync, concept, sample_images)
        image_bytes_list = self._extract_gemini_image_bytes(response)
        urls: list[str] = []
        for image_bytes in image_bytes_list:
            image_path = self._save_image_locally(image_bytes, aspect_ratio=concept.aspect_ratio)
            if image_path:
                urls.append(f"/output/{image_path}")
        if not urls:
            print("[VERTEX_AI] Gemini image response did not include usable image bytes")
        return urls

    async def _call_imagen_api(self, concept: VisualConcept, sample_images: list[str] | None = None) -> list[str]:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._generate_images_sync, concept, sample_images)
        images = self._extract_images(response)
        if not images:
            print(f"[VERTEX_AI] No images in response (type={type(response).__name__})")
            return []
        urls: list[str] = []
        for image in images:
            image_bytes = self._extract_image_bytes(image)
            if not image_bytes:
                continue
            image_path = self._save_image_locally(image_bytes, aspect_ratio=concept.aspect_ratio)
            if image_path:
                urls.append(f"/output/{image_path}")
        if not urls:
            print(f"[VERTEX_AI] Parsed {len(images)} image object(s) but extracted 0 usable byte payloads")
        return urls

    def _extract_images(self, response) -> list:
        images = getattr(response, "images", None)
        if images:
            return list(images)
        try:
            # Some Vertex SDK responses are list-like rather than exposing `.images`.
            items = list(response)
            return items
        except Exception:
            return []

    def _generate_images_sync(self, concept: VisualConcept, sample_images: list[str] | None = None):
        kwargs = {
            "prompt": concept.generation_prompt,
            "number_of_images": 1,
            "aspect_ratio": self._get_vertex_aspect_ratio(concept.aspect_ratio),
        }
        if sample_images:
            base_image = self._build_base_image(sample_images)
            if base_image is not None and self._edit_client is not None:
                print("[VERTEX_AI] Using sample image as base_image for edit mode")
                try:
                    return self._edit_client.edit_image(
                        prompt=concept.generation_prompt,
                        base_image=base_image,
                        edit_mode="product-image",
                        number_of_images=1,
                    )
                except Exception as exc:
                    print(f"[VERTEX_AI] edit_image with base sample failed, fallback to text-only generation: {exc}")
            elif base_image is not None and self._edit_client is None:
                print("[VERTEX_AI] Edit model unavailable; using text-only generation fallback")
        return self._client.generate_images(**kwargs)

    def _generate_gemini_image_sync(self, concept: VisualConcept, sample_images: list[str] | None = None):
        contents: list = [concept.generation_prompt]
        attached_count = 0
        for source in sample_images or []:
            try:
                image_bytes = self._read_reference_source(source)
                normalized = self._normalize_image_bytes_for_vertex(image_bytes)
                contents.append(
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": base64.b64encode(normalized).decode("utf-8"),
                        }
                    }
                )
                attached_count += 1
            except Exception as exc:
                print(f"[VERTEX_AI] Failed to include sample image for Gemini image mode: {exc}")
        if sample_images:
            print(f"[VERTEX_AI] Gemini image mode attached {attached_count}/{len(sample_images)} reference image(s)")

        config = {
            "response_modalities": ["IMAGE", "TEXT"],
            "image_config": {
                "aspect_ratio": self._get_vertex_aspect_ratio(concept.aspect_ratio),
            },
        }

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                return self._gemini_client.models.generate_content(
                    model=self._model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                error_str = str(exc)
                is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str

                if is_rate_limit and attempt < max_retries:
                    wait_time = 15 * (2 ** attempt)  # 15s, 30s, 60s
                    print(f"[VERTEX_AI] 429 rate limit on attempt {attempt+1}/{max_retries+1}, waiting {wait_time}s before retry...")
                    import time
                    time.sleep(wait_time)
                    continue

                if attempt == max_retries:
                    print(f"[VERTEX_AI] All {max_retries+1} attempts failed: {exc}")
                    # Last resort: try without config
                    try:
                        return self._gemini_client.models.generate_content(
                            model=self._model_name,
                            contents=contents,
                        )
                    except Exception as final_exc:
                        print(f"[VERTEX_AI] Final fallback also failed: {final_exc}")
                        raise final_exc

                print(f"[VERTEX_AI] Non-retryable error: {exc}")
                raise exc

    def _extract_gemini_image_bytes(self, response) -> list[bytes]:
        extracted: list[bytes] = []
        for candidate in self._extract_images(response):
            image_bytes = self._extract_image_bytes(candidate)
            if image_bytes:
                extracted.append(image_bytes)
        if extracted:
            return extracted

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                data = getattr(inline, "data", None)
                if isinstance(data, bytes) and data:
                    extracted.append(data)
                elif isinstance(data, str) and data:
                    try:
                        extracted.append(base64.b64decode(data))
                    except (binascii.Error, ValueError):
                        continue
        return extracted

    def _build_base_image(self, sample_images: list[str]):
        if not sample_images:
            return None
        source = sample_images[0]
        try:
            image_bytes = self._read_reference_source(source)
            normalized = self._normalize_image_bytes_for_vertex(image_bytes)
            return VertexImage(image_bytes=normalized)
        except Exception as exc:
            print(f"[VERTEX_AI] Failed to parse sample image as base image: {exc}")
            return None

    def _normalize_image_bytes_for_vertex(self, image_bytes: bytes) -> bytes:
        """Normalize user-provided sample image to a safe RGB PNG for Vertex edit mode."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Remove alpha and convert to RGB for broader backend compatibility.
            if img.mode not in {"RGB", "L"}:
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")

            # Constrain maximum side to reduce backend processing failures.
            max_side = 1536
            if max(img.size) > max_side:
                img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()

    def _extract_image_bytes(self, image_obj) -> bytes | None:
        candidates = (
            getattr(image_obj, "_image_bytes", None),
            getattr(image_obj, "data", None),
            getattr(image_obj, "image_bytes", None),
            getattr(image_obj, "bytes", None),
        )
        for candidate in candidates:
            if isinstance(candidate, bytes) and candidate:
                return candidate
        return None

    def _read_reference_source(self, source: str) -> bytes:
        if source.startswith("data:"):
            encoded = source.split(",", 1)[1]
            try:
                return base64.b64decode(encoded)
            except (binascii.Error, ValueError) as exc:
                raise ValueError(f"Invalid base64 data URL: {exc}") from exc

        if source.startswith("/output/"):
            relative = source[len("/output/"):].lstrip("/")
            output_path = Path("output") / relative
            if output_path.exists():
                return output_path.read_bytes()

        path = Path(source)
        if path.exists():
            return path.read_bytes()

        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            response = httpx.get(source, timeout=20.0, follow_redirects=True)
            response.raise_for_status()
            return response.content

        raise ValueError(f"Unsupported reference image source: {source}")

    def _save_image_locally(self, image_data: bytes, *, aspect_ratio: str) -> str | None:
        try:
            from datetime import datetime
            import hashlib

            output_dir = Path("output") / "vertex_ai_images"
            output_dir.mkdir(parents=True, exist_ok=True)

            normalized_bytes = self._normalize_generated_image_aspect_ratio(image_data, aspect_ratio=aspect_ratio)
            timestamp = datetime.now().isoformat().replace(":", "-")
            content_hash = hashlib.md5(normalized_bytes).hexdigest()[:8]
            provider_prefix = "gemini" if self._provider == "gemini_image" else "imagen"
            filename = f"{provider_prefix}_{timestamp}_{content_hash}.png"
            filepath = output_dir / filename
            filepath.write_bytes(normalized_bytes)
            return f"vertex_ai_images/{filename}"
        except Exception as e:
            print(f"[VERTEX_AI] Failed to save image locally: {e}")
            return None

    def _normalize_generated_image_aspect_ratio(self, image_data: bytes, *, aspect_ratio: str) -> bytes:
        target_size = self._TARGET_SIZES.get(aspect_ratio, self._TARGET_SIZES["9:16"])
        with Image.open(io.BytesIO(image_data)) as img:
            if img.mode not in {"RGB", "L"}:
                img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")
            fitted = self._cover_resize(img, target_size)
            buf = io.BytesIO()
            fitted.save(buf, format="PNG", optimize=True)
            return buf.getvalue()

    @staticmethod
    def _cover_resize(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
        target_width, target_height = target_size
        scale = max(target_width / image.width, target_height / image.height)
        resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
        left = max(0, (resized.width - target_width) // 2)
        top = max(0, (resized.height - target_height) // 2)
        return resized.crop((left, top, left + target_width, top + target_height))

    def _get_vertex_aspect_ratio(self, aspect_ratio: str) -> str:
        ratio_map = {
            "1:1": "1:1",
            # Vertex Imagen in current SDK path may reject 4:5; use vertical-safe fallback.
            "4:5": "9:16",
            "9:16": "9:16",
            "16:9": "16:9",
            "1.91:1": "1.91:1",
        }
        return ratio_map.get(aspect_ratio, "9:16")

    async def aclose(self) -> None:
        return None
