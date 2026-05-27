from collections import Counter

from app.models import NormalizedReelData, ReelReference, ReelTrend


class TrendDetector:
    def __init__(self, storage=None) -> None:
        self._storage = storage

    def detect(self, *, brief: str, trending_reels: list[ReelReference], competitor_reels: list[ReelReference], normalized_reels: list[NormalizedReelData] | None = None, niche: str | None = None, audience: str | None = None) -> list[ReelTrend]:
        memory = self._load_memory()
        normalized = normalized_reels or []
        sources = self._collect_sources(brief, trending_reels, competitor_reels, normalized, niche, audience)
        tokens = Counter(self._tokens(" ".join(sources)))
        rows: list[ReelTrend] = []
        style_tokens = Counter()
        for reel in normalized:
            style_tokens.update([token.lower() for token in reel.caption_patterns if token])
            style_tokens.update([token.lower() for token in reel.retention_signals if token])
            style_tokens.update([token.lower() for token in reel.visual_hooks if token])

        rows.append(self._trend_from_keywords("Outcome-first demo", 90, "early growth", ["show", "proof", "result"], ["Show the result immediately", "Use proof in the first 3 seconds"], ["Outcome-first openers", "Proof-led captions"], ["tight crop", "vertical framing"], sources))
        rows.append(self._trend_from_keywords("Contrarian hook", 87, "moderate", ["stop", "wrong", "mistake"], ["Lead with a contradiction", "Use tension before explanation"], ["Curiosity hooks", "Myth-busting captions"], ["fast cuts", "hard text resets"], sources))
        rows.append(self._trend_from_keywords("Comment bait utility", 74, "high", ["comment", "save", "follow"], ["Ask for the next step", "Invite a specific response"], ["Prompt-style captions", "Pinned-comment follow-ups"], ["tight zooms", "caption overlays"], sources))
        if style_tokens:
            common_styles = [token for token, _ in style_tokens.most_common(4)]
            rows.append(
                ReelTrend(
                    trend_name="Pattern library crossover",
                    trend_score=min(95, 66 + len(common_styles) * 5),
                    saturation_level="moderate" if len(common_styles) > 2 else "early growth",
                    viral_probability=min(100, 70 + len(common_styles) * 6),
                    best_niches=[niche or "cross-niche", "education", "creator economy"],
                    hook_examples=[f"Use {common_styles[0]} in first-frame text"] if common_styles else ["first-frame pattern break"],
                    caption_patterns=[f"{token} caption sequence" for token in common_styles[:2]],
                    editing_styles=[f"{token} editing rhythm" for token in common_styles[:3]],
                    retention_levers=["frequent visual resets", "proof in first 5 seconds"],
                    source_count=len(normalized),
                )
            )

        if tokens:
            top_keywords = [token for token, _ in tokens.most_common(6)]
            rows[0].hook_examples = [f"Hook terms: {', '.join(top_keywords[:3])}"]
            rows[0].caption_patterns = [f"Caption terms: {', '.join(top_keywords[3:6])}"]

        if memory:
            for row in rows:
                row.source_count = max(row.source_count, len(memory))
                row.trend_score = min(100, row.trend_score + 2)

        self._save_memory(memory, rows)
        rows.sort(key=lambda item: (item.viral_probability, item.trend_score, item.source_count), reverse=True)
        return rows[:5]

    def _trend_from_keywords(
        self,
        name: str,
        trend_score: int,
        saturation_level: str,
        keywords: list[str],
        retention_levers: list[str],
        caption_patterns: list[str],
        editing_styles: list[str],
        sources: list[str],
    ) -> ReelTrend:
        lower_sources = " ".join(sources).lower()
        source_count = sum(1 for keyword in keywords if keyword in lower_sources)
        viral_probability = min(100, trend_score + source_count * 4)
        return ReelTrend(
            trend_name=name,
            trend_score=trend_score,
            saturation_level=saturation_level,
            viral_probability=viral_probability,
            best_niches=["education", "founders", "creator economy"],
            hook_examples=[f"{name} example"],
            caption_patterns=caption_patterns,
            editing_styles=editing_styles,
            retention_levers=retention_levers,
            source_count=source_count,
        )

    def _collect_sources(
        self,
        brief: str,
        trending_reels: list[ReelReference],
        competitor_reels: list[ReelReference],
        normalized_reels: list[NormalizedReelData],
        niche: str | None,
        audience: str | None,
    ) -> list[str]:
        sources = [brief, niche or "", audience or ""]
        for reference in [*trending_reels, *competitor_reels]:
            sources.extend([reference.caption or "", reference.transcript or "", reference.audio_name or "", reference.username or ""])
            sources.extend(reference.comments)
        for reel in normalized_reels:
            sources.extend([reel.caption or "", reel.transcript or "", reel.audio_name or "", reel.username or reel.competitor_name or ""])
            sources.extend(reel.comments)
        return [source for source in sources if source]

    def _load_memory(self) -> list[dict]:
        if self._storage and hasattr(self._storage, "load_instagram_trend_memory"):
            return self._storage.load_instagram_trend_memory()
        return []

    def _save_memory(self, memory: list[dict], trends: list[ReelTrend]) -> None:
        if not self._storage or not hasattr(self._storage, "save_instagram_trend_memory"):
            return
        payload = list(memory)
        payload.extend([trend.model_dump(mode="json") for trend in trends])
        self._storage.save_instagram_trend_memory(payload[-50:])

    @staticmethod
    def _tokens(value: str) -> list[str]:
        import re

        return re.findall(r"[a-z0-9']+", value.lower())
