import asyncio
import base64
import inspect
import io
import re
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from app.core.config import Settings
from app.models import (
    AdCopy,
    CampaignPackage,
    ConceptGenerationResponse,
    CreativeAsset,
    CreativeInput,
    CreativeStatus,
    GeneratedCreative,
    Hook,
    MessagingAngle,
    Objective,
    Platform,
    RenderedAd,
    VisualConcept,
)
from app.providers.groq_llm import GroqLLMProvider
from app.providers.huggingface import HuggingFaceClient
from app.providers.nanobanana import NanoBananaClient
from app.providers.vertex_ai import VertexAIClient
from app.services.instagram_analyzer import InstagramAnalyzer
from app.services.instagram_engine import InstagramDirectorEngine
from app.services.instagram_ingestion import InstagramIngestionService
from app.services.reels_director import ReelsDirector
from app.services.retention_scorer import RetentionScorer
from app.services.composition import AdCompositionService, build_brand_assets
from app.services.database import CampaignDatabase
from app.services.download_artifacts import CreativeDownloadArtifactExporter
from app.services.exporter import MetaAdsCsvExporter
from app.services.ingestors.competitor_tracker import CompetitorTracker
from app.services.ingestors.instagram_ingestor import InstagramIngestor
from app.services.ingestors.trend_collector import TrendCollector
from app.services.viral_pattern_engine import ViralPatternEngine
from app.services.generators import AdCopyGenerator, HookGenerator, MessagingAngleGenerator, VisualConceptGenerator
from app.services.script_writer import ScriptWriter
from app.services.trend_detector import TrendDetector
from app.services.image_fallback import LocalImageFallbackService
from app.services.preview import AdPreviewGenerator
from app.services.scoring import CreativeScoringService
from app.services.storage import CampaignStorage


class CreativeDirectorEngine:
    def __init__(
        self,
        *,
        hook_generator: HookGenerator,
        angle_generator: MessagingAngleGenerator,
        ad_copy_generator: AdCopyGenerator,
        visual_concept_generator: VisualConceptGenerator,
        nanobanana_client: NanoBananaClient,
        scoring_service: CreativeScoringService,
        storage: CampaignStorage,
        database: CampaignDatabase | None = None,
        vertex_client: VertexAIClient | None = None,
        hf_client: HuggingFaceClient | None = None,
        composition_service: AdCompositionService | None = None,
        preview_generator: AdPreviewGenerator | None = None,
        exporter: MetaAdsCsvExporter | None = None,
        image_fallback_service: LocalImageFallbackService | None = None,
    ) -> None:
        self._hook_generator = hook_generator
        self._angle_generator = angle_generator
        self._ad_copy_generator = ad_copy_generator
        self._visual_concept_generator = visual_concept_generator
        self._nanobanana_client = nanobanana_client
        self._vertex_client = vertex_client
        self._hf_client = hf_client
        self._scoring_service = scoring_service
        self._storage = storage
        self._database = database
        self._composition_service = composition_service
        self._preview_generator = preview_generator
        self._exporter = exporter
        self._image_fallback_service = image_fallback_service
        self._image_provider_timeout_seconds = 600.0

    async def generate_concepts(self, payload: CreativeInput) -> ConceptGenerationResponse:
        hooks_task = asyncio.create_task(self._hook_generator.generate(payload))
        angles_task = asyncio.create_task(self._angle_generator.generate(payload))
        hooks, angles = await asyncio.gather(hooks_task, angles_task)

        ad_copies = await self._ad_copy_generator.generate(payload, hooks, angles)
        visual_concepts = await self._visual_concept_generator.generate(payload, hooks, angles, ad_copies)

        return ConceptGenerationResponse(
            hooks=hooks,
            angles=angles,
            ad_copies=ad_copies,
            visual_concepts=visual_concepts,
        )

    async def generate_single_image(self, payload: CreativeInput, concept: VisualConcept) -> GeneratedCreative:
        print("\n" + "="*50)
        print("[BACKEND] CREATIVE GENERATION IMAGE REFERENCES CHECK")
        if payload.logo_image:
            print(f"  - logo_image: PRESENT (len: {len(payload.logo_image)}) -> {payload.logo_image[:80]}...")
        else:
            print("  - logo_image: NOT PRESENT")
        
        if payload.sample_images:
            print(f"  - sample_images count: {len(payload.sample_images)}")
            for idx, img in enumerate(payload.sample_images):
                print(f"    * Sample [{idx}]: len {len(img)} -> {img[:80]}...")
        else:
            print("  - sample_images: NOT PRESENT")
        print("="*50 + "\n")

        has_reference_images = bool(payload.sample_images)
        generation_references = self._build_generation_references(payload)
        has_generation_references = bool(generation_references)
        
        vertex_client_obj = self._vertex_client
        vertex_provider = (getattr(vertex_client_obj, "_provider", "imagen") if vertex_client_obj else "imagen")
        vertex_runtime_client = (
            getattr(vertex_client_obj, "_gemini_client", None)
            if vertex_provider == "gemini_image"
            else getattr(vertex_client_obj, "_client", None)
        )
        vertex_ready = bool(
            vertex_client_obj
            and getattr(vertex_client_obj, "_project_id", None)
            and vertex_runtime_client is not None
        )
        hf_ready = bool(self._hf_client and getattr(self._hf_client, "_api_key", None))

        generated_creative = None

        if vertex_ready:
            print(f"[INFO] Using Vertex AI for concept {concept.concept_id}")
            results = await self._generate_images_with_timeout(
                self._vertex_client.generate_batch(
                    [concept],
                    platform=payload.platform,
                    sample_images=generation_references,
                )
            )
            if results: generated_creative = results[0]
        elif has_generation_references and hf_ready:
            print(f"[INFO] Using HuggingFace for concept {concept.concept_id}")
            results = await self._generate_images_with_timeout(
                self._hf_client.generate_batch(
                    [concept],
                    platform=payload.platform,
                    sample_images=generation_references,
                )
            )
            if results: generated_creative = results[0]
        elif has_generation_references:
            print(
                "[WARNING] No image provider available for reference images. "
                f"Vertex ready: {vertex_ready}, HF ready: {hf_ready}"
            )

        if (
            not has_reference_images
            and (not generated_creative or generated_creative.status in (CreativeStatus.FAILED, CreativeStatus.SKIPPED))
            and self._nanobanana_client
            and self._has_real_api_key(getattr(self._nanobanana_client, "_api_key", None))
        ):
            results = await self._generate_images_with_timeout(
                self._nanobanana_client.generate_batch(
                    [concept],
                    platform=payload.platform,
                    sample_images=generation_references,
                )
            )
            if results: generated_creative = results[0]

        if (
            not has_reference_images
            and (not generated_creative or generated_creative.status in (CreativeStatus.FAILED, CreativeStatus.SKIPPED))
            and getattr(self, "_hf_client", None)
            and getattr(self._hf_client, "_api_key", None)
        ):
            results = await self._generate_images_with_timeout(
                self._hf_client.generate_batch(
                    [concept],
                    platform=payload.platform,
                    sample_images=generation_references,
                )
            )
            if results: generated_creative = results[0]
        if (
            not has_reference_images
            and (not generated_creative or generated_creative.status in (CreativeStatus.FAILED, CreativeStatus.SKIPPED))
            and self._image_fallback_service
        ):
            results = self._image_fallback_service.generate_batch(
                payload=payload,
                concepts=[concept],
                existing=[],
            )
            if results: generated_creative = results[0]

        if not generated_creative:
            generated_creative = GeneratedCreative(
                concept_id=concept.concept_id,
                provider="unknown",
                status=CreativeStatus.FAILED,
                prompt=concept.generation_prompt,
                error="No provider available or generation timed out",
                image_urls=[],
            )
            
        return generated_creative

    async def score_and_package(
        self,
        payload: CreativeInput,
        hooks: list[Hook],
        angles: list[MessagingAngle],
        ad_copies: list[AdCopy],
        visual_concepts: list[VisualConcept],
        generated_creatives: list[GeneratedCreative],
        client_email: str | None = None,
        is_guest: bool = False,
    ) -> CampaignPackage:
        scored_creatives = await self._scoring_service.score(
            payload,
            visual_concepts,
            ad_copies,
            generated_creatives,
        )
        ad_copies = await self._scoring_service.score_ad_copies(
            payload,
            visual_concepts,
            ad_copies,
            generated_creatives,
            scored_creatives=scored_creatives,
        )

        created_at = datetime.now(tz=UTC)
        campaign_name = payload.campaign_name or self._default_campaign_name(payload)
        campaign_slug = slugify(campaign_name)
        brand_assets = build_brand_assets(
            brand_name=payload.brand_name,
            logo_image=payload.logo_image,
            brand_colors=payload.brand_colors,
            brand_fonts=payload.brand_fonts,
        )
        campaign_dir = self._storage.build_campaign_dir(campaign_slug, created_at)
        creative_assets = self._build_creative_assets(
            campaign_name=campaign_name,
            campaign_slug=campaign_slug,
            platform=payload.platform,
            objective=payload.objective,
            hooks=hooks,
            angles=angles,
            ad_copies=ad_copies,
            visual_concepts=visual_concepts,
            generated_creatives=generated_creatives,
            scored_creatives=scored_creatives,
        )
        creative_assets = self._render_assets(
            creative_assets=creative_assets,
            campaign_dir=campaign_dir,
            brand_assets=brand_assets,
            brand_name=payload.brand_name,
        )
        export_rows = self._exporter.export(assets=creative_assets, campaign_dir=campaign_dir) if self._exporter else []
        download_exporter = CreativeDownloadArtifactExporter()
        for asset in creative_assets:
            if asset.rendered_ad:
                download_exporter.export(asset=asset, campaign_dir=campaign_dir)

        package = CampaignPackage(
            campaign_name=campaign_name,
            campaign_slug=campaign_slug,
            created_at=created_at,
            input=payload,
            hooks=hooks,
            angles=angles,
            ad_copies=ad_copies,
            visual_concepts=visual_concepts,
            generated_creatives=generated_creatives,
            scored_creatives=scored_creatives,
            creative_assets=creative_assets,
            brand_assets=brand_assets,
            export_rows=export_rows,
        )
        output_directory = self._storage.save_package(package)
        package.output_directory = output_directory

        if self._database:
            self._database.save_campaign(package, client_email=client_email, is_guest=is_guest)

        return package

    async def generate_campaign(self, payload: CreativeInput, client_email: str | None = None, is_guest: bool = False) -> CampaignPackage:
        concepts_resp = await self.generate_concepts(payload)
        
        # Parallel image generation
        tasks = [self.generate_single_image(payload, concept) for concept in concepts_resp.visual_concepts]
        generated_creatives = list(await asyncio.gather(*tasks))
            
        return await self.score_and_package(
            payload=payload,
            hooks=concepts_resp.hooks,
            angles=concepts_resp.angles,
            ad_copies=concepts_resp.ad_copies,
            visual_concepts=concepts_resp.visual_concepts,
            generated_creatives=generated_creatives,
            client_email=client_email,
            is_guest=is_guest,
        )

    @staticmethod
    def _build_generation_references(payload: CreativeInput) -> list[str]:
        references: list[str] = []
        seen: set[str] = set()
        for source in [*(payload.sample_images or []), payload.logo_image]:
            if not source:
                continue
            normalized = source.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            references.append(normalized)
        return references

    async def _generate_images_with_timeout(self, coroutine):
        """Await image generation. Per-image timeouts are handled in generate_batch."""
        try:
            return await coroutine
        except Exception as e:
            import traceback
            print(f"[ERROR] Image generation batch failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            return []

    @staticmethod
    def _has_real_api_key(value: str | None) -> bool:
        if not value:
            return False
        normalized = value.strip().lower()
        return "your_real_key_here" not in normalized and "placeholder" not in normalized

    def _render_assets(
        self,
        *,
        creative_assets: list[CreativeAsset],
        campaign_dir,
        brand_assets,
        brand_name: str,
    ) -> list[CreativeAsset]:
        if not self._composition_service:
            return creative_assets

        rendered_assets: list[CreativeAsset] = []
        for asset in creative_assets:
            image_source = next(iter(asset.generated_creative.image_urls), None)
            if not image_source:
                rendered_assets.append(asset)
                continue

            try:
                image_bytes = self._composition_service._read_binary(image_source)
                image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                rendered_dir = Path(campaign_dir) / "rendered"
                rendered_dir.mkdir(parents=True, exist_ok=True)
                output_path = rendered_dir / f"{asset.concept_id}.png"
                image.save(output_path, format="PNG", optimize=True)

                rendered_ad = RenderedAd(
                    concept_id=asset.concept_id,
                    image_path=str(output_path),
                    image_base64=None,
                    width=image.width,
                    height=image.height,
                    headline_lines=[asset.headline or asset.hook_text],
                    body_lines=[asset.primary_text or ""],
                    supporting_text=asset.description,
                    cta_text=asset.cta or "Learn More",
                    brand_name=brand_name,
                )
                preview = (
                    self._preview_generator.generate(asset=asset.model_copy(update={"rendered_ad": rendered_ad}), campaign_dir=campaign_dir)
                    if self._preview_generator
                    else None
                )
                if preview and preview.image_path:
                    preview.image_base64 = None
                        
                rendered_assets.append(asset.model_copy(update={"rendered_ad": rendered_ad, "preview": preview}))
            except Exception as exc:
                print(f"[WARN] Failed to save generated final ad for {asset.concept_id}: {type(exc).__name__}: {exc}")
                rendered_assets.append(asset)

        return rendered_assets

    def get_top_creatives(self, *, limit: int | None, platform: Platform | None):
        if self._database:
            return self._database.get_top_creatives(limit=limit, platform=platform)
        return self._storage.get_top_creatives(limit=limit, platform=platform)

    def get_campaign_history(self, *, limit: int | None, platform: Platform | None):
        if self._database:
            return self._database.get_campaign_history(limit=limit, platform=platform)
        return self._storage.get_campaign_history(limit=limit, platform=platform)


    def _build_creative_assets(
        self,
        *,
        campaign_name: str,
        campaign_slug: str,
        platform: Platform,
        objective: Objective,
        hooks: list[Hook],
        angles: list[MessagingAngle],
        ad_copies,
        visual_concepts: list[VisualConcept],
        generated_creatives: list[GeneratedCreative],
        scored_creatives,
    ) -> list[CreativeAsset]:
        hook_lookup = {hook.text: hook for hook in hooks}
        angle_lookup = {angle.name: angle for angle in angles}
        copy_lookup = {(copy.hook_text, copy.angle_name): copy for copy in ad_copies}
        generated_lookup = {
            creative.concept_id: creative
            for creative in generated_creatives
            if creative.status == CreativeStatus.GENERATED
        }
        score_lookup = {score.concept_id: score for score in scored_creatives}

        successful_count = len(generated_lookup)
        failed_count = len(generated_creatives) - successful_count
        print(f"[DEBUG] Building assets: {len(visual_concepts)} concepts, {len(generated_creatives)} generated ({successful_count} success, {failed_count} failed), {len(scored_creatives)} scored")
        print(f"[DEBUG] Generated lookup keys: {list(generated_lookup.keys())[:5]}")
        print(f"[DEBUG] Score lookup keys: {list(score_lookup.keys())[:5]}")

        assets: list[CreativeAsset] = []
        for concept in visual_concepts:
            copy = copy_lookup.get((concept.hook_text, concept.angle_name)) or ad_copies[0]
            hook = hook_lookup.get(concept.hook_text)
            angle = angle_lookup.get(concept.angle_name)
            generated = generated_lookup.get(concept.concept_id)
            score = score_lookup.get(concept.concept_id)
            
            if generated is None:
                print(f"[WARN] Missing generated creative for concept {concept.concept_id}")
            if score is None:
                print(f"[WARN] Missing score for concept {concept.concept_id}")
            
            if generated is None or score is None:
                continue
            
            assets.append(
                CreativeAsset(
                    campaign_name=campaign_name,
                    campaign_slug=campaign_slug,
                    platform=platform,
                    objective=objective,
                    concept_id=concept.concept_id,
                    hook_type=hook.type if hook else None,
                    hook_text=concept.hook_text,
                    angle_name=concept.angle_name,
                    target_emotion=angle.target_emotion if angle else None,
                    primary_text=copy.primary_text,
                    headline=copy.headline,
                    description=copy.description,
                    cta=copy.cta,
                    visual_concept=concept,
                    generated_creative=generated,
                    score=score,
                )
            )
        print(f"[DEBUG] Created {len(assets)} assets (filtered from {len(visual_concepts)} concepts)")
        assets.sort(key=lambda item: item.score.total_score, reverse=True)
        return assets

    @staticmethod
    def _default_campaign_name(payload: CreativeInput) -> str:
        return f"{payload.brand_name} {payload.objective.value} {payload.platform.value}"


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        llm = GroqLLMProvider(settings)
        nanobanana = NanoBananaClient(settings)
        storage = CampaignStorage(settings)
        database = CampaignDatabase(settings)
        vertex_client = VertexAIClient(settings)
        hf_client = HuggingFaceClient(settings)
        composition_service = AdCompositionService(settings.output_root)
        preview_generator = AdPreviewGenerator()
        exporter = MetaAdsCsvExporter()
        image_fallback_service = LocalImageFallbackService()
        instagram_ingestor = InstagramIngestor(timeout_seconds=settings.image_provider_timeout_seconds)
        trend_collector = TrendCollector()
        competitor_tracker = CompetitorTracker()
        pattern_engine = ViralPatternEngine()
        trend_detector = TrendDetector(storage=storage)
        retention_scorer = RetentionScorer()
        instagram_analyzer = InstagramAnalyzer(
            llm=llm,
            pattern_engine=pattern_engine,
            trend_detector=trend_detector,
            scorer=retention_scorer,
            storage=storage,
        )
        script_writer = ScriptWriter(
            llm=llm,
            analyzer=instagram_analyzer,
            scorer=retention_scorer,
            trend_detector=trend_detector,
        )
        reels_director = ReelsDirector(llm=llm, script_writer=script_writer, analyzer=instagram_analyzer)

        self.engine = CreativeDirectorEngine(
            hook_generator=HookGenerator(llm),
            angle_generator=MessagingAngleGenerator(llm),
            ad_copy_generator=AdCopyGenerator(llm),
            visual_concept_generator=VisualConceptGenerator(llm),
            nanobanana_client=nanobanana,
            scoring_service=CreativeScoringService(llm),
            storage=storage,
            database=database,
            vertex_client=vertex_client,
            hf_client=hf_client,
            composition_service=composition_service,
            preview_generator=preview_generator,
            exporter=exporter,
            image_fallback_service=image_fallback_service,
        )
        self.instagram_engine = InstagramDirectorEngine(
            trend_detector=trend_detector,
            analyzer=instagram_analyzer,
            script_writer=script_writer,
            director=reels_director,
            scorer=retention_scorer,
            pattern_engine=pattern_engine,
        )
        self.instagram_ingestion = InstagramIngestionService(
            ingestor=instagram_ingestor,
            trend_collector=trend_collector,
            competitor_tracker=competitor_tracker,
            storage=storage,
        )
        self.engine._image_provider_timeout_seconds = settings.image_provider_timeout_seconds
        self._closables = [llm, nanobanana, vertex_client, hf_client, database, instagram_ingestor]

    async def aclose(self) -> None:
        for resource in self._closables:
            close_method = getattr(resource, "aclose", None)
            if callable(close_method):
                result = close_method()
                if inspect.isawaitable(result):
                    await result
                continue
            sync_close = getattr(resource, "close", None)
            if callable(sync_close):
                sync_close()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "campaign"
