from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Platform(str, Enum):
    META = "meta"
    GOOGLE = "google"
    TIKTOK = "tiktok"


class Objective(str, Enum):
    CONVERSIONS = "conversions"
    TRAFFIC = "traffic"
    AWARENESS = "awareness"


class HookType(str, Enum):
    CURIOSITY = "curiosity"
    FEAR_BASED = "fear_based"
    BENEFIT_DRIVEN = "benefit_driven"
    CONTRARIAN = "contrarian"
    SOCIAL_PROOF = "social_proof"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class CreativeStatus(str, Enum):
    GENERATED = "generated"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


class CreativeInput(BaseModel):
    brand_name: str = Field(..., min_length=2)
    product_description: str = Field(..., min_length=10)
    target_audience: str = Field(..., min_length=3)
    platform: Platform
    objective: Objective
    tone: str = Field(..., min_length=2)
    key_benefits: list[str] = Field(..., min_length=1)
    competitors: list[str] = Field(default_factory=list)
    visual_style: str | None = None
    sample_images: list[str] = Field(default_factory=list)
    reference_similarity: float = Field(default=0.5, ge=0.0, le=1.0)
    brand_colors: list[str] = Field(default_factory=list)
    brand_fonts: list[str] = Field(default_factory=list)
    logo_image: str | None = None
    extra_details: str | None = None

    campaign_name: str | None = None
    hook_count: int = Field(default=5, ge=1, le=10)
    angle_count: int = Field(default=3, ge=1, le=10)
    copy_count: int = Field(default=5, ge=1, le=10)
    concept_count: int = Field(default=5, ge=1, le=10)

    @field_validator("brand_name", "product_description", "target_audience", "tone", "visual_style")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())

    @field_validator("key_benefits", "competitors")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        return [" ".join(item.split()) for item in values if item and item.strip()]


class Hook(BaseModel):
    type: HookType
    text: str = Field(..., min_length=5)
    rationale: str = Field(..., min_length=10)


class HookSet(BaseModel):
    hooks: list[Hook] = Field(..., min_length=1)


class MessagingAngle(BaseModel):
    name: str = Field(..., min_length=3)
    description: str = Field(..., min_length=10)
    target_emotion: str = Field(..., min_length=3)
    use_case: str = Field(..., min_length=5)


class MessagingAngleSet(BaseModel):
    angles: list[MessagingAngle] = Field(..., min_length=1)


class AdCopy(BaseModel):
    copy_id: str | None = None
    hook_text: str = Field(..., min_length=5)
    angle_name: str = Field(..., min_length=3)
    primary_text: str = Field(..., min_length=10)
    headline: str = Field(..., min_length=3)
    cta: str = Field(..., min_length=2)
    description: str = Field(default="", min_length=0)
    total_score: int | None = Field(default=None, ge=0, le=100)
    score_rank: int | None = Field(default=None, ge=1)
    score_rationale: str | None = None


class AdCopySet(BaseModel):
    ad_copies: list[AdCopy] = Field(..., min_length=1)


class VisualConceptDraft(BaseModel):
    hook_text: str = Field(..., min_length=5)
    angle_name: str = Field(..., min_length=3)
    scene_description: str = Field(..., min_length=10)
    camera_angle: str = Field(..., min_length=3)
    background_setting: str = Field(..., min_length=5)
    color_palette: list[str] = Field(..., min_length=1)
    mood: str = Field(..., min_length=3)
    style_reference: str = Field(..., min_length=3)
    aspect_ratio: str = Field(..., min_length=3)
    media_type: MediaType = MediaType.IMAGE


class VisualConceptSet(BaseModel):
    visual_concepts: list[VisualConceptDraft] = Field(..., min_length=1)


class VisualConcept(VisualConceptDraft):
    concept_id: str
    generation_prompt: str = Field(..., min_length=15)


class GeneratedCreative(BaseModel):
    concept_id: str
    provider: str
    provider_api_version: str | None = None
    status: CreativeStatus
    prompt: str
    image_urls: list[str] = Field(default_factory=list)
    video_urls: list[str] = Field(default_factory=list)
    error: str | None = None
    raw_response: dict[str, Any] | None = None


class BrandAssets(BaseModel):
    primary_color: str = "#111111"
    secondary_color: str = "#F4F1EA"
    accent_color: str = "#E85D04"
    text_color: str = "#FFFFFF"
    font_family: str | None = None
    cta_font_family: str | None = None
    logo_image: str | None = None


class RenderedAd(BaseModel):
    concept_id: str
    image_path: str
    width: int
    height: int
    headline_lines: list[str] = Field(default_factory=list)
    body_lines: list[str] = Field(default_factory=list)
    supporting_text: str | None = None
    cta_text: str
    brand_name: str
    image_base64: str | None = None


class AdPreview(BaseModel):
    concept_id: str
    platform: Platform
    image_path: str
    width: int
    height: int
    image_base64: str | None = None


class ExportRow(BaseModel):
    campaign_name: str
    ad_set_name: str
    ad_name: str
    platform: Platform
    primary_text: str
    headline: str
    description: str
    cta: str
    image_path: str
    preview_path: str | None = None


class LLMCreativeEvaluation(BaseModel):
    clarity: int = Field(..., ge=0, le=100)
    persuasion: int = Field(..., ge=0, le=100)
    cta_alignment: int = Field(..., ge=0, le=100)
    platform_fit: int = Field(..., ge=0, le=100)
    rationale: str = Field(..., min_length=10)


class CreativeScore(BaseModel):
    concept_id: str
    emotional_intensity: int = Field(..., ge=0, le=100)
    clarity: int = Field(..., ge=0, le=100)
    uniqueness: int = Field(..., ge=0, le=100)
    platform_fit: int = Field(..., ge=0, le=100)
    persuasion: int = Field(default=0, ge=0, le=100)
    cta_alignment: int = Field(default=0, ge=0, le=100)
    total_score: int = Field(..., ge=0, le=100)
    rank: int | None = None
    rationale: str = Field(..., min_length=10)


class CreativeAsset(BaseModel):
    campaign_name: str
    campaign_slug: str
    platform: Platform
    objective: Objective
    concept_id: str
    hook_type: HookType | None = None
    hook_text: str
    angle_name: str
    target_emotion: str | None = None
    primary_text: str | None = None
    headline: str | None = None
    description: str | None = None
    cta: str | None = None
    visual_concept: VisualConcept
    generated_creative: GeneratedCreative
    score: CreativeScore
    rendered_ad: RenderedAd | None = None
    preview: AdPreview | None = None


class CampaignPackage(BaseModel):
    campaign_name: str
    campaign_slug: str
    created_at: datetime
    input: CreativeInput
    hooks: list[Hook]
    angles: list[MessagingAngle]
    ad_copies: list[AdCopy]
    visual_concepts: list[VisualConcept]
    generated_creatives: list[GeneratedCreative]
    scored_creatives: list[CreativeScore]
    creative_assets: list[CreativeAsset]
    brand_assets: BrandAssets | None = None
    export_rows: list[ExportRow] = Field(default_factory=list)
    output_directory: str | None = None


class TopCreativeItem(BaseModel):
    campaign_name: str
    campaign_slug: str
    platform: Platform
    concept_id: str
    total_score: int
    primary_text: str | None = None
    headline: str | None = None
    description: str | None = None
    cta: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    video_urls: list[str] = Field(default_factory=list)
    rendered_image_path: str | None = None
    preview_image_path: str | None = None
    output_directory: str


class TopCreativesResponse(BaseModel):
    items: list[TopCreativeItem]


class CampaignHistoryItem(BaseModel):
    campaign_name: str
    campaign_slug: str
    created_at: str
    platform: Platform
    objective: str
    top_score: int
    total_creatives: int
    hooks: list[Hook] = Field(default_factory=list)
    angles: list[MessagingAngle] = Field(default_factory=list)
    visual_concepts: list[VisualConcept] = Field(default_factory=list)
    creatives: list[dict[str, Any]] = Field(default_factory=list)
    output_directory: str


class CampaignHistoryResponse(BaseModel):
    items: list[CampaignHistoryItem]


class ConceptGenerationResponse(BaseModel):
    hooks: list[Hook]
    angles: list[MessagingAngle]
    ad_copies: list[AdCopy]
    visual_concepts: list[VisualConcept]


class ImageGenerationRequest(BaseModel):
    payload: CreativeInput
    concept: VisualConcept


class ScoringRequest(BaseModel):
    payload: CreativeInput
    hooks: list[Hook]
    angles: list[MessagingAngle]
    ad_copies: list[AdCopy]
    visual_concepts: list[VisualConcept]
    generated_creatives: list[GeneratedCreative]
