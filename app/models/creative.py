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


class ReelAnalysisCategory(str, Enum):
    VISUAL_HOOK = "visual_hook"
    OPENING_LINE = "opening_line"
    EMOTIONAL_TRIGGER = "emotional_trigger"
    PACING_STYLE = "pacing_style"
    SCENE_DENSITY = "scene_density"
    CTA_STYLE = "cta_style"
    CAPTION_PATTERN = "caption_pattern"
    AUDIO_TREND = "audio_trend"
    COMPETITOR_PATTERN = "competitor_pattern"
    TRANSITION_PATTERN = "transition_pattern"


class ReelReference(BaseModel):
    username: str | None = None
    reel_url: str | None = None
    caption: str | None = None
    transcript: str | None = None
    comments: list[str] = Field(default_factory=list)
    audio_name: str | None = None
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)


class ReelEngagementMetrics(BaseModel):
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0.0)
    retention_proxy: float | None = Field(default=None, ge=0.0)


class NormalizedReelData(BaseModel):
    reel_id: str
    source: str = Field(default="instagram")
    source_type: str = Field(default="competitor")
    username: str | None = None
    competitor_name: str | None = None
    reel_url: str | None = None
    caption: str = Field(default="")
    transcript: str | None = None
    hook_text: str | None = None
    hook_type: str | None = None
    audio_name: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    comment_sentiment: str | None = None
    posted_at: datetime | None = None
    posting_hour: int | None = Field(default=None, ge=0, le=23)
    engagement: ReelEngagementMetrics = Field(default_factory=ReelEngagementMetrics)
    retention_signals: list[str] = Field(default_factory=list)
    visual_hooks: list[str] = Field(default_factory=list)
    caption_patterns: list[str] = Field(default_factory=list)
    trend_labels: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    def to_reference(self) -> ReelReference:
        return ReelReference(
            username=self.username or self.competitor_name,
            reel_url=self.reel_url,
            caption=self.caption,
            transcript=self.transcript,
            comments=self.comments,
            audio_name=self.audio_name,
            views=self.engagement.views,
            likes=self.engagement.likes,
            shares=self.engagement.shares,
            saves=self.engagement.saves,
        )


class ReelTrendSnapshot(BaseModel):
    snapshot_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    niche: str | None = None
    audience: str | None = None
    trend_name: str = Field(default="")
    trend_score: int = Field(default=0, ge=0, le=100)
    viral_probability: int = Field(default=0, ge=0, le=100)
    saturation_level: str = Field(default="unknown")
    source_reel_ids: list[str] = Field(default_factory=list)
    hook_library: list[str] = Field(default_factory=list)
    caption_patterns: list[str] = Field(default_factory=list)
    audio_patterns: list[str] = Field(default_factory=list)
    posting_time_patterns: list[str] = Field(default_factory=list)
    momentum_delta: float = Field(default=0.0)
    benchmark_score: int = Field(default=0, ge=0, le=100)
    notes: str | None = None


class InstagramIngestionRequest(BaseModel):
    reel_urls: list[str] = Field(default_factory=list)
    instagram_usernames: list[str] = Field(default_factory=list)
    competitor_reels: list[ReelReference] = Field(default_factory=list)
    trending_reels: list[ReelReference] = Field(default_factory=list)
    niche: str | None = None
    audience: str | None = None
    max_reels: int = Field(default=20, ge=1, le=100)
    include_comments: bool = True
    include_metrics: bool = True
    force_refresh: bool = False
    cache_ttl_seconds: int = Field(default=1800, ge=0)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=120)
    job_name: str | None = None
    async_job: bool = True


class InstagramIngestionJob(BaseModel):
    job_id: str
    status: str = Field(default="queued")
    progress: int = Field(default=0, ge=0, le=100)
    message: str = Field(default="queued")
    request: InstagramIngestionRequest
    result_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    error: str | None = None


class InstagramIngestionResult(BaseModel):
    reels: list[NormalizedReelData] = Field(default_factory=list)
    trend_snapshots: list[ReelTrendSnapshot] = Field(default_factory=list)
    competitor_insights: list["CompetitorReelInsight"] = Field(default_factory=list)
    benchmark_score: int = Field(default=0, ge=0, le=100)
    hook_library: list[str] = Field(default_factory=list)
    caption_patterns: list[str] = Field(default_factory=list)
    hashtag_patterns: list[str] = Field(default_factory=list)
    posting_time_patterns: list[str] = Field(default_factory=list)
    audio_patterns: list[str] = Field(default_factory=list)
    momentum_score: float = Field(default=0.0)
    stored_snapshot_ids: list[str] = Field(default_factory=list)


class ReelInsight(BaseModel):
    category: ReelAnalysisCategory
    insight: str = Field(..., min_length=5)
    why_it_works: str = Field(..., min_length=5)
    evidence: list[str] = Field(default_factory=list)
    score: int = Field(default=0, ge=0, le=100)
    recommendation: str = Field(..., min_length=5)


class CompetitorReelInsight(BaseModel):
    competitor: str = Field(..., min_length=1)
    reel_url: str | None = None
    hook_format: str = Field(..., min_length=3)
    winning_pattern: str = Field(..., min_length=5)
    cta_strategy: str = Field(..., min_length=3)
    comment_sentiment: str | None = None
    why_it_wins: str = Field(..., min_length=5)
    reusable_formula: str = Field(..., min_length=5)
    score: int = Field(default=0, ge=0, le=100)


class ReelTrend(BaseModel):
    trend_name: str = Field(..., min_length=3)
    trend_score: int = Field(..., ge=0, le=100)
    saturation_level: str = Field(..., min_length=3)
    viral_probability: int = Field(..., ge=0, le=100)
    best_niches: list[str] = Field(default_factory=list)
    hook_examples: list[str] = Field(default_factory=list)
    caption_patterns: list[str] = Field(default_factory=list)
    editing_styles: list[str] = Field(default_factory=list)
    retention_levers: list[str] = Field(default_factory=list)
    source_count: int = Field(default=0, ge=0)


class ReelSceneBeat(BaseModel):
    second_range: str = Field(..., min_length=1)
    scene: str = Field(..., min_length=5)
    camera_direction: str = Field(..., min_length=3)
    b_roll: list[str] = Field(default_factory=list)
    text_overlay: list[str] = Field(default_factory=list)
    editing_notes: list[str] = Field(default_factory=list)
    sound_design: list[str] = Field(default_factory=list)
    facial_expression: str | None = None
    emotional_intent: str = Field(..., min_length=3)
    retention_note: str = Field(..., min_length=5)
    transition_timing: str | None = None
    interruption_pattern: bool = False


class ReelScoreBreakdown(BaseModel):
    hook_strength: int = Field(default=0, ge=0, le=100)
    virality: int = Field(default=0, ge=0, le=100)
    retention: int = Field(default=0, ge=0, le=100)
    shareability: int = Field(default=0, ge=0, le=100)
    emotional_impact: int = Field(default=0, ge=0, le=100)
    curiosity_gap: int = Field(default=0, ge=0, le=100)
    thumbnail_quality: int = Field(default=0, ge=0, le=100)
    cta_effectiveness: int = Field(default=0, ge=0, le=100)
    total_score: int = Field(default=0, ge=0, le=100)
    rationale: str = Field(default="", min_length=0)


class ReelScript(BaseModel):
    title: str = Field(default="", min_length=0)
    viral_probability_score: int = Field(default=0, ge=0, le=100)
    hook_strength_score: int = Field(default=0, ge=0, le=100)
    audience_retention_prediction: int = Field(default=0, ge=0, le=100)
    spoken_script: str = Field(default="", min_length=0)
    scene_by_scene_direction: list[ReelSceneBeat] = Field(default_factory=list)
    camera_direction: str = Field(default="", min_length=0)
    b_roll_suggestions: list[str] = Field(default_factory=list)
    caption_overlays: list[str] = Field(default_factory=list)
    editing_notes: list[str] = Field(default_factory=list)
    sound_design_suggestions: list[str] = Field(default_factory=list)
    cta: str = Field(default="", min_length=0)
    instagram_caption: str = Field(default="", min_length=0)
    hashtag_suggestions: list[str] = Field(default_factory=list)
    thumbnail_text: str = Field(default="", min_length=0)
    emotional_progression: list[str] = Field(default_factory=list)
    retention_strategy_explanation: str = Field(default="", min_length=0)
    second_by_second_timeline: list[ReelSceneBeat] = Field(default_factory=list)
    retention_critical_moments: list[str] = Field(default_factory=list)
    dopamine_spikes: list[str] = Field(default_factory=list)
    interruption_pattern_moments: list[str] = Field(default_factory=list)


class InstagramReelsRequest(BaseModel):
    brief: str = Field(..., min_length=3)
    brand_name: str | None = None
    niche: str | None = None
    audience: str | None = None
    creator_persona: str | None = None
    goal: str | None = None
    tone: str | None = None
    duration_seconds: int = Field(default=30, ge=5, le=180)
    hook_angle: str | None = None
    call_to_action: str | None = None
    transcript: str | None = None
    caption: str | None = None
    audio_trend_hint: str | None = None
    editing_style_hint: str | None = None
    extra_context: str | None = None
    reel_links: list[str] = Field(default_factory=list)
    instagram_usernames: list[str] = Field(default_factory=list)
    competitor_reels: list[ReelReference] = Field(default_factory=list)
    trending_reels: list[ReelReference] = Field(default_factory=list)
    reference_reels: list[ReelReference] = Field(default_factory=list)
    normalized_reels: list[NormalizedReelData] = Field(default_factory=list)
    competitor_comments: list[str] = Field(default_factory=list)
    hashtag_examples: list[str] = Field(default_factory=list)


class InstagramAnalyzeReelRequest(InstagramReelsRequest):
    pass


class InstagramAnalyzeCompetitorRequest(InstagramReelsRequest):
    pass


class InstagramDetectTrendsRequest(InstagramReelsRequest):
    pass


class InstagramGenerateScriptRequest(InstagramReelsRequest):
    pass


class InstagramDirectReelRequest(InstagramGenerateScriptRequest):
    pass


class InstagramScoreReelRequest(InstagramReelsRequest):
    candidate_hook: str | None = None
    candidate_script: str | None = None
    thumbnail_text: str | None = None
    instagram_caption: str | None = None


class InstagramReelsResponse(BaseModel):
    title: str = Field(default="Instagram Reels Intelligence")
    summary: str = Field(default="")
    brand_name: str | None = None
    niche: str | None = None
    audience: str | None = None
    viral_probability_score: int = Field(default=0, ge=0, le=100)
    hook_strength_score: int = Field(default=0, ge=0, le=100)
    audience_retention_prediction: int = Field(default=0, ge=0, le=100)
    retention_score: int = Field(default=0, ge=0, le=100)
    hook_alternatives: list[str] = Field(default_factory=list)
    analysis: list[ReelInsight] = Field(default_factory=list)
    competitor_winning_reels: list[CompetitorReelInsight] = Field(default_factory=list)
    trend_objects: list[ReelTrend] = Field(default_factory=list)
    top_performing_patterns: list[str] = Field(default_factory=list)
    content_gaps: list[str] = Field(default_factory=list)
    reusable_winning_formulas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    full_script: list[ReelSceneBeat] = Field(default_factory=list)
    script: ReelScript = Field(default_factory=ReelScript)
    director_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    instagram_caption: str = Field(default="")
    hashtags: list[str] = Field(default_factory=list)
    thumbnail_text: str = Field(default="")
    scores: ReelScoreBreakdown = Field(default_factory=ReelScoreBreakdown)
    second_by_second_timeline: list[ReelSceneBeat] = Field(default_factory=list)
    retention_critical_moments: list[str] = Field(default_factory=list)
    dopamine_spikes: list[str] = Field(default_factory=list)
    interruption_pattern_moments: list[str] = Field(default_factory=list)
    audio_trend: str | None = None
    caption_pattern: str | None = None
