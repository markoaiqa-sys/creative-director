from __future__ import annotations

from collections import Counter, defaultdict
import re

from app.models import CompetitorReelInsight, NormalizedReelData


class CompetitorTracker:
    def benchmark(self, reels: list[NormalizedReelData]) -> tuple[list[CompetitorReelInsight], int, list[str], list[str]]:
        groups: dict[str, list[NormalizedReelData]] = defaultdict(list)
        for reel in reels:
            key = reel.competitor_name or reel.username or reel.source_type or "competitor"
            groups[key].append(reel)

        insights: list[CompetitorReelInsight] = []
        top_patterns: list[str] = []
        content_gaps: list[str] = []
        benchmark_scores: list[int] = []

        for competitor, items in groups.items():
            hook_formats = Counter(self._hook_format(item) for item in items)
            caption_patterns = Counter(pattern for item in items for pattern in item.caption_patterns)
            avg_engagement = self._avg([self._engagement_score(item) for item in items])
            sentiment = self._dominant_sentiment(item.comment_sentiment for item in items)
            winning_pattern = hook_formats.most_common(1)[0][0] if hook_formats else "Hook-first opening"
            reusable_formula = "Hook -> proof -> payoff -> CTA"
            cta_strategy = self._cta_strategy(items)
            score = min(100, round(avg_engagement + len(caption_patterns) * 4 + len(items) * 2))
            benchmark_scores.append(score)
            insights.append(
                CompetitorReelInsight(
                    competitor=competitor,
                    reel_url=items[0].reel_url,
                    hook_format=winning_pattern,
                    winning_pattern=self._winning_pattern_description(items),
                    cta_strategy=cta_strategy,
                    comment_sentiment=sentiment,
                    why_it_wins=self._why_it_wins(items, avg_engagement),
                    reusable_formula=reusable_formula,
                    score=score,
                )
            )
            top_patterns.extend([pattern for pattern, _ in caption_patterns.most_common(3)])

            if not any("social proof" in pattern.lower() for pattern in caption_patterns):
                content_gaps.append(f"{competitor}: limited social proof framing")
            if not any("comparison" in pattern.lower() or "vs" in pattern.lower() for pattern in caption_patterns):
                content_gaps.append(f"{competitor}: weak comparison framing")

        benchmark_score = min(100, round(self._avg(benchmark_scores))) if benchmark_scores else 0
        return insights, benchmark_score, self._dedupe(top_patterns), self._dedupe(content_gaps)

    @staticmethod
    def _hook_format(reel: NormalizedReelData) -> str:
        hook = reel.hook_text or reel.caption or ""
        words = re.findall(r"[a-z0-9']+", hook.lower())
        return " ".join(words[:8]) or "hook-first opener"

    @staticmethod
    def _engagement_score(reel: NormalizedReelData) -> int:
        metrics = reel.engagement
        likes = metrics.likes or 0
        shares = metrics.shares or 0
        saves = metrics.saves or 0
        comments = metrics.comments or 0
        views = metrics.views or 0
        if views > 0:
            rate = ((likes + shares + saves + comments) / views) * 100
            return round(min(100.0, rate))
        return round(min(100.0, (metrics.engagement_rate or 0.0) + (metrics.retention_proxy or 0.0) / 2))

    @staticmethod
    def _dominant_sentiment(sentiments) -> str:
        counts = Counter(sentiments)
        if not counts:
            return "unknown"
        return counts.most_common(1)[0][0]

    @staticmethod
    def _cta_strategy(items: list[NormalizedReelData]) -> str:
        text = " ".join((item.caption or "") for item in items).lower()
        if any(token in text for token in ["comment", "dm", "save", "follow"]):
            return "Engagement CTA"
        if any(token in text for token in ["learn", "get", "download", "watch"]):
            return "Conversion CTA"
        return "Soft CTA"

    @staticmethod
    def _winning_pattern_description(items: list[NormalizedReelData]) -> str:
        first = items[0]
        signals = ", ".join(first.retention_signals[:3]) if first.retention_signals else "neutral pacing"
        return f"Repeated hook and proof pattern with {signals}."

    @staticmethod
    def _why_it_wins(items: list[NormalizedReelData], avg_engagement: int) -> str:
        if avg_engagement >= 60:
            return "It converts attention into engagement with a clear promise and a fast proof sequence."
        return "It is legible, repeatable, and easy for the audience to process quickly."

    @staticmethod
    def _avg(values: list[int]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            normalized = item.strip().lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(item)
        return ordered
