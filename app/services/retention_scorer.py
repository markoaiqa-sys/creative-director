import re

from app.models import InstagramReelsRequest, NormalizedReelData, ReelInsight, ReelScoreBreakdown, ReelScript, ReelTrend


class RetentionScorer:
    def score(
        self,
        *,
        request: InstagramReelsRequest,
        analysis: list[ReelInsight],
        trends: list[ReelTrend],
        script: ReelScript | None = None,
        normalized_reels: list[NormalizedReelData] | None = None,
    ) -> ReelScoreBreakdown:
        text = " ".join([
            request.brief,
            request.hook_angle or "",
            request.goal or "",
            request.transcript or "",
            request.caption or "",
            script.spoken_script if script else "",
            script.instagram_caption if script else "",
            script.thumbnail_text if script else "",
        ]).lower()

        hook_strength = self._score_hook(text, analysis)
        virality = self._score_virality(text, trends)
        retention = self._score_retention(text, analysis, trends, request.duration_seconds)
        shareability = self._score_shareability(text)
        emotional_impact = self._score_emotion(text)
        curiosity_gap = self._score_curiosity(text)
        thumbnail_quality = self._score_thumbnail(script.thumbnail_text if script else request.hook_angle or request.brief)
        cta_effectiveness = self._score_cta(request.call_to_action or (script.cta if script else ""))
        if normalized_reels:
            retention = min(100, retention + min(8, len(normalized_reels) * 2))
            virality = min(100, virality + min(6, len([item for item in normalized_reels if item.engagement.likes or item.engagement.shares])) )

        total = round(
            hook_strength * 0.18
            + virality * 0.16
            + retention * 0.20
            + shareability * 0.12
            + emotional_impact * 0.10
            + curiosity_gap * 0.10
            + thumbnail_quality * 0.08
            + cta_effectiveness * 0.06
        )

        rationale = (
            f"Retention is driven by {self._dominant_driver(hook_strength, retention, curiosity_gap)}. "
            f"The concept scores best when the hook, pacing, and CTA align with the audience's attention pattern."
        )

        return ReelScoreBreakdown(
            hook_strength=hook_strength,
            virality=virality,
            retention=retention,
            shareability=shareability,
            emotional_impact=emotional_impact,
            curiosity_gap=curiosity_gap,
            thumbnail_quality=thumbnail_quality,
            cta_effectiveness=cta_effectiveness,
            total_score=min(100, max(0, total)),
            rationale=rationale,
        )

    def _score_hook(self, text: str, analysis: list[ReelInsight]) -> int:
        score = 50
        if any(insight.category.value == "opening_line" for insight in analysis):
            score += 12
        if any(token in text for token in ["why", "stop", "mistake", "secret", "before", "after"]):
            score += 15
        if len(text.split()) <= 40:
            score += 8
        return min(100, score)

    def _score_virality(self, text: str, trends: list[ReelTrend]) -> int:
        score = 52
        if any(trend.viral_probability >= 80 for trend in trends):
            score += 14
        if any(token in text for token in ["save", "comment", "share", "replay"]):
            score += 12
        if "contrarian" in text or "proof" in text:
            score += 8
        return min(100, score)

    def _score_retention(self, text: str, analysis: list[ReelInsight], trends: list[ReelTrend], duration_seconds: int) -> int:
        score = 55
        if duration_seconds <= 35:
            score += 10
        if any(insight.category.value in {"pacing_style", "scene_density"} for insight in analysis):
            score += 10
        if any("fast" in item.editing_styles for item in trends):
            score += 7
        if len(re.findall(r"[.!?]", text)) >= 2:
            score += 6
        return min(100, score)

    def _score_shareability(self, text: str) -> int:
        score = 45
        if any(token in text for token in ["template", "framework", "formula", "hack", "mistake"]):
            score += 18
        if "you" in text and "your" in text:
            score += 8
        return min(100, score)

    def _score_emotion(self, text: str) -> int:
        score = 45
        if any(token in text for token in ["relief", "confidence", "fear", "desire", "frustration", "excited"]):
            score += 20
        if any(token in text for token in ["finally", "quickly", "faster", "easy"]):
            score += 8
        return min(100, score)

    def _score_curiosity(self, text: str) -> int:
        score = 50
        if any(token in text for token in ["why", "what", "how", "secret", "mistake", "wrong"]):
            score += 20
        if "?" in text:
            score += 6
        return min(100, score)

    def _score_thumbnail(self, thumbnail_text: str) -> int:
        score = 50
        if thumbnail_text and len(thumbnail_text.split()) <= 5:
            score += 18
        if any(token in thumbnail_text.lower() for token in ["stop", "why", "secret", "mistake", "viral"]):
            score += 12
        return min(100, score)

    def _score_cta(self, call_to_action: str) -> int:
        score = 45
        if call_to_action and len(call_to_action.split()) <= 4:
            score += 20
        if any(token in call_to_action.lower() for token in ["comment", "save", "follow", "dm", "click"]):
            score += 15
        return min(100, score)

    @staticmethod
    def _dominant_driver(hook_strength: int, retention: int, curiosity_gap: int) -> str:
        values = {
            "hook strength": hook_strength,
            "retention": retention,
            "curiosity gap": curiosity_gap,
        }
        return max(values, key=values.get)