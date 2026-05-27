from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
import re

from app.models import NormalizedReelData, ReelTrend, ReelTrendSnapshot


class TrendCollector:
    def collect(
        self,
        reels: list[NormalizedReelData],
        *,
        niche: str | None = None,
        audience: str | None = None,
        previous_snapshots: list[dict] | None = None,
    ) -> tuple[list[ReelTrendSnapshot], list[ReelTrend], dict[str, list[str] | float | int]]:
        previous_snapshots = previous_snapshots or []
        hooks = Counter(self._clean_phrase(reel.hook_text or reel.caption) for reel in reels if (reel.hook_text or reel.caption))
        hashtags = Counter(tag.lower() for reel in reels for tag in reel.hashtags)
        audio = Counter((reel.audio_name or "unknown").lower() for reel in reels if reel.audio_name)
        hours = Counter(reel.posting_hour for reel in reels if reel.posting_hour is not None)
        caption_patterns = Counter(pattern for reel in reels for pattern in reel.caption_patterns)
        retention_signals = Counter(signal for reel in reels for signal in reel.retention_signals)
        comment_sentiment = Counter(reel.comment_sentiment or "unknown" for reel in reels)

        hook_library = [hook for hook, _ in hooks.most_common(12)]
        caption_pattern_list = [pattern for pattern, _ in caption_patterns.most_common(10)]
        hashtag_patterns = [tag for tag, _ in hashtags.most_common(12)]
        audio_patterns = [name for name, _ in audio.most_common(8)]
        posting_time_patterns = [f"hour_{hour}" for hour, _ in hours.most_common(6)]
        momentum_score = self._momentum_score(reels, previous_snapshots)

        snapshots: list[ReelTrendSnapshot] = []
        trend_objects: list[ReelTrend] = []
        for index, (pattern, count) in enumerate(hooks.most_common(3), start=1):
            snapshot_id = f"snapshot-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{index}"
            trend_score = min(100, 65 + count * 7 + len(hashtag_patterns[:3]) * 2)
            viral_probability = min(100, trend_score + 8)
            saturation_level = self._saturation_level(count, len(reels))
            snapshots.append(
                ReelTrendSnapshot(
                    snapshot_id=snapshot_id,
                    niche=niche,
                    audience=audience,
                    trend_name=pattern or f"trend-{index}",
                    trend_score=trend_score,
                    viral_probability=viral_probability,
                    saturation_level=saturation_level,
                    source_reel_ids=[reel.reel_id for reel in reels[: max(1, min(len(reels), 10))]],
                    hook_library=hook_library[:8],
                    caption_patterns=caption_pattern_list[:8],
                    audio_patterns=audio_patterns[:6],
                    posting_time_patterns=posting_time_patterns[:6],
                    momentum_delta=momentum_score,
                    benchmark_score=min(100, trend_score + len(retention_signals)),
                    notes=f"Sentiment mix: {dict(comment_sentiment)}",
                    created_at=datetime.now(tz=UTC),
                )
            )
            trend_objects.append(
                ReelTrend(
                    trend_name=pattern or f"trend-{index}",
                    trend_score=trend_score,
                    saturation_level=saturation_level,
                    viral_probability=viral_probability,
                    best_niches=[niche] if niche else ["education", "founders", "creator economy"],
                    hook_examples=hook_library[:3],
                    caption_patterns=caption_pattern_list[:3],
                    editing_styles=["fast cuts", "text resets"],
                    retention_levers=list(retention_signals.keys())[:5],
                    source_count=len(reels),
                )
            )

        summary = {
            "hook_library": hook_library,
            "caption_patterns": caption_pattern_list,
            "hashtag_patterns": hashtag_patterns,
            "posting_time_patterns": posting_time_patterns,
            "audio_patterns": audio_patterns,
            "momentum_score": momentum_score,
        }
        return snapshots, trend_objects, summary

    @staticmethod
    def _clean_phrase(value: str) -> str:
        words = re.findall(r"[a-z0-9']+", value.lower())
        return " ".join(words[:8])

    @staticmethod
    def _saturation_level(count: int, total: int) -> str:
        if total <= 0:
            return "unknown"
        ratio = count / float(total)
        if ratio >= 0.6:
            return "high"
        if ratio >= 0.3:
            return "moderate"
        return "low"

    @staticmethod
    def _momentum_score(reels: list[NormalizedReelData], previous_snapshots: list[dict]) -> float:
        current_score = sum((reel.engagement.engagement_rate or 0) + (reel.engagement.retention_proxy or 0) for reel in reels)
        if not reels:
            return 0.0
        current_average = current_score / len(reels)
        previous_average = 0.0
        if previous_snapshots:
            scores = [float(item.get("momentum_delta", 0.0)) for item in previous_snapshots if isinstance(item, dict)]
            if scores:
                previous_average = sum(scores) / len(scores)
        return round(current_average - previous_average, 2)
