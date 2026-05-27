from datetime import UTC, datetime

from app.models import (
    CompetitorReelInsight,
    InstagramAnalyzeReelRequest,
    InstagramReelsRequest,
    InstagramReelsResponse,
    NormalizedReelData,
)
from app.providers.groq_llm import GroqLLMProvider
from app.services.instagram_prompts import INSTAGRAM_SYSTEM_PROMPT, analysis_prompt, competitor_prompt
from app.services.retention_scorer import RetentionScorer
from app.services.trend_detector import TrendDetector
from app.services.viral_pattern_engine import ViralPatternEngine


class InstagramAnalyzer:
    def __init__(
        self,
        llm: GroqLLMProvider | None,
        pattern_engine: ViralPatternEngine,
        trend_detector: TrendDetector,
        scorer: RetentionScorer,
        storage=None,
    ) -> None:
        self._llm = llm
        self._pattern_engine = pattern_engine
        self._trend_detector = trend_detector
        self._scorer = scorer
        self._storage = storage

    async def analyze_reel(self, request: InstagramAnalyzeReelRequest) -> InstagramReelsResponse:
        return await self._build_response(request=request, mode="analyze")

    async def analyze_competitor(self, request: InstagramReelsRequest) -> InstagramReelsResponse:
        return await self._build_response(request=request, mode="competitor")

    async def _build_response(self, *, request: InstagramReelsRequest, mode: str) -> InstagramReelsResponse:
        base = self._heuristic_response(request)
        if not self._llm:
            return base

        prompt = analysis_prompt(request) if mode == "analyze" else competitor_prompt(request)
        try:
            structured = await self._llm.structured_completion(
                instructions=INSTAGRAM_SYSTEM_PROMPT,
                user_prompt=prompt,
                response_model=InstagramReelsResponse,
            )
            return self._merge(base, structured)
        except Exception:
            return base

    def _heuristic_response(self, request: InstagramReelsRequest) -> InstagramReelsResponse:
        reference_pool = [
            *request.reference_reels,
            *request.competitor_reels,
            *request.trending_reels,
            *[reel.to_reference() for reel in request.normalized_reels],
        ]
        quality = self._quality_summary(request)
        analysis = self._pattern_engine.build_insights(
            brief=request.brief,
            references=reference_pool,
            niche=request.niche,
            audience=request.audience,
        )
        trend_objects = self._trend_detector.detect(
            brief=request.brief,
            trending_reels=request.trending_reels,
            competitor_reels=request.competitor_reels,
            normalized_reels=request.normalized_reels,
            niche=request.niche,
            audience=request.audience,
        )
        score = self._scorer.score(request=request, analysis=analysis, trends=trend_objects)
        competitor_sources = list(request.competitor_reels)
        if not competitor_sources:
            competitor_sources = [item.to_reference() for item in request.normalized_reels if item.source_type in {"competitor", "reference"}][:8]
        if not competitor_sources and request.instagram_usernames:
            competitor_sources = [NormalizedReelData(reel_id=f"user-{idx}", username=name, competitor_name=name).to_reference() for idx, name in enumerate(request.instagram_usernames, start=1)]
        competitor_insights = [self._competitor_from_reference(reference, request.niche) for reference in competitor_sources[:8]]
        response = InstagramReelsResponse(
            title=f"{request.brand_name or 'Instagram'} Reel Intelligence",
            summary=self._summary(request),
            brand_name=request.brand_name,
            niche=request.niche,
            audience=request.audience,
            data_quality_score=quality["score"],
            confidence_label=quality["label"],
            warning_message=quality["warning"],
            pipeline_steps=[
                "Reel sources ingested",
                "Hook and viral pattern analysis completed",
                "Trend signals clustered",
                "Competitor formulas compared",
                "Retention and virality scored",
            ],
            viral_probability_score=max(score.virality, score.total_score),
            hook_strength_score=score.hook_strength,
            audience_retention_prediction=score.retention,
            retention_score=score.retention,
            hook_alternatives=self._pattern_engine.build_hook_alternatives(request.brief, request.audience, request.niche),
            analysis=analysis,
            competitor_winning_reels=competitor_insights,
            trend_objects=trend_objects,
            top_performing_patterns=self._pattern_engine.build_reusable_formulas(analysis),
            content_gaps=self._pattern_engine.build_content_gaps(request.competitor_reels),
            reusable_winning_formulas=self._pattern_engine.build_reusable_formulas(analysis),
            recommendations=[item.recommendation for item in analysis[:5]],
            assumptions=self._build_assumptions(request),
            instagram_caption=request.caption or self._caption_from_request(request),
            hashtags=self._hashtags_from_request(request),
            thumbnail_text=request.hook_angle or request.brief[:36],
            scores=score,
            retention_curve=self._build_retention_curve(score.retention, quality["score"]),
            replay_spike_curve=self._build_replay_curve(score.shareability, score.curiosity_gap),
            audio_trend=trend_objects[0].trend_name if trend_objects else request.audio_trend_hint,
            caption_pattern=analysis[6].insight if len(analysis) > 6 else None,
        )
        self._persist_memory(request, response)
        return response

    @staticmethod
    def _merge(base: InstagramReelsResponse, overlay: InstagramReelsResponse) -> InstagramReelsResponse:
        data = base.model_dump(mode="json")
        overlay_data = overlay.model_dump(mode="json")
        for key, value in overlay_data.items():
            if value not in (None, "", [], {}):
                data[key] = value
        return InstagramReelsResponse.model_validate(data)

    @staticmethod
    def _summary(request: InstagramReelsRequest) -> str:
        parts = [request.brief]
        if request.niche:
            parts.append(f"Niche: {request.niche}")
        if request.audience:
            parts.append(f"Audience: {request.audience}")
        if request.goal:
            parts.append(f"Goal: {request.goal}")
        return " | ".join(parts)

    @staticmethod
    def _quality_summary(request: InstagramReelsRequest) -> dict[str, int | str | None]:
        normalized = request.normalized_reels or []
        reel_count = len(normalized)
        transcript_count = len([item for item in normalized if item.transcript])
        caption_count = len([item for item in normalized if item.caption])
        metric_count = len([item for item in normalized if item.engagement and any([
            item.engagement.views,
            item.engagement.likes,
            item.engagement.shares,
            item.engagement.saves,
        ])])
        visual_signal_count = len([item for item in normalized if item.visual_hooks or item.retention_signals or item.caption_patterns])
        direct_refs = len(request.reference_reels) + len(request.competitor_reels) + len(request.trending_reels)
        manual_transcript = 1 if request.transcript and request.transcript.strip() else 0
        manual_caption = 1 if request.caption and request.caption.strip() else 0
        manual_hook = 1 if request.hook_angle and request.hook_angle.strip() else 0
        manual_context_score = manual_transcript * 28 + manual_caption * 18 + manual_hook * 16

        score = min(
            100,
            reel_count * 8
            + transcript_count * 14
            + caption_count * 8
            + metric_count * 8
            + visual_signal_count * 10
            + direct_refs * 5
            + manual_context_score,
        )
        if request.single_reel_mode and reel_count <= 1 and manual_context_score > 0:
            score = min(100, score + 12)
        if score >= 75:
            label = "High"
            warning = None
        elif score >= 45:
            label = "Medium"
            warning = (
                "Analysis is directionally useful. For single-reel mode, add transcript, caption, and opening hook to increase confidence."
                if request.single_reel_mode
                else "Analysis is directionally useful, but more reels, transcripts, or metrics would improve accuracy."
            )
        else:
            label = "Low"
            warning = (
                "Single-reel mode needs richer context. Add transcript, caption text, and opening hook to improve analysis."
                if request.single_reel_mode
                else "Not enough reel data for strong analysis yet. Add more reels, competitor samples, or richer transcript/caption inputs."
            )
        return {"score": score, "label": label, "warning": warning}

    @staticmethod
    def _build_assumptions(request: InstagramReelsRequest) -> list[str]:
        assumptions = []
        if not request.normalized_reels:
            assumptions.append("Live Instagram performance data was not directly fetched in this run.")
        if not request.competitor_reels and not request.instagram_usernames:
            assumptions.append("Competitor intelligence is inferred from the brief and niche, not direct reel URLs.")
        if request.trending_reels:
            assumptions.append("Trend objects are biased toward the provided trend samples.")
        if request.normalized_reels:
            assumptions.append(f"Analysis includes {len(request.normalized_reels)} normalized reel records from ingestion context.")
        if request.single_reel_mode:
            assumptions.append("Single reel deep analysis mode is active; confidence is boosted by manual transcript/caption/hook context.")
        return assumptions

    @staticmethod
    def _build_retention_curve(retention_score: int, quality_score: int) -> list[int]:
        opening = min(100, max(62, retention_score + 14))
        mid = max(28, opening - max(18, 32 - quality_score // 4))
        payoff = max(24, mid - 8)
        cta = max(18, payoff - 6)
        return [opening, max(opening - 12, mid + 6), mid, max(mid - 5, payoff + 4), payoff, cta]

    @staticmethod
    def _build_replay_curve(shareability: int, curiosity_gap: int) -> list[int]:
        base = max(10, curiosity_gap // 3)
        spike = min(100, base + shareability // 2)
        return [base, min(100, base + 8), spike, max(base, spike - 16), min(100, base + 12), max(8, base - 2)]

    @staticmethod
    def _caption_from_request(request: InstagramReelsRequest) -> str:
        if request.goal:
            return f"{request.brief} {request.goal}."
        return f"{request.brief}."

    @staticmethod
    def _hashtags_from_request(request: InstagramReelsRequest) -> list[str]:
        base = [request.niche, request.goal, request.brand_name]
        tags = [f"#{token.lower().replace(' ', '')}" for token in base if token]
        if not tags:
            tags = ["#instagramreels", "#contentstrategy", "#viralreels"]
        return tags[:6]

    def _persist_memory(self, request: InstagramReelsRequest, response: InstagramReelsResponse) -> None:
        if not self._storage:
            return

        try:
            analysis_rows = self._storage.load_instagram_analysis_memory()
            analysis_rows.append(
                {
                    "brief": request.brief,
                    "brand_name": request.brand_name,
                    "niche": request.niche,
                    "viral_probability_score": response.viral_probability_score,
                    "hook_strength_score": response.hook_strength_score,
                    "retention_score": response.retention_score,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            )
            self._storage.save_instagram_analysis_memory(analysis_rows[-100:])

            hook_rows = self._storage.load_instagram_hook_library()
            hook_rows.append(
                {
                    "brief": request.brief,
                    "brand_name": request.brand_name,
                    "hooks": response.hook_alternatives,
                    "top_patterns": response.top_performing_patterns,
                }
            )
            self._storage.save_instagram_hook_library(hook_rows[-100:])
        except Exception:
            return

    @staticmethod
    def _competitor_from_reference(reference, niche: str | None) -> CompetitorReelInsight:
        winning_pattern = reference.caption or reference.transcript or f"{reference.username or 'competitor'} uses a repeatable hook structure"
        return CompetitorReelInsight(
            competitor=reference.username or niche or "competitor",
            reel_url=reference.reel_url,
            hook_format=reference.caption or "Hook-first opener",
            winning_pattern=winning_pattern,
            cta_strategy="Comment, save, or follow CTA",
            comment_sentiment="positive interest",
            why_it_wins="It makes the promise obvious early and keeps the viewer moving toward the payoff.",
            reusable_formula="Hook -> proof -> payoff -> CTA",
            score=82,
        )
