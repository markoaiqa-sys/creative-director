from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from html import unescape
from typing import Any

from app.models import ReelEngagementMetrics, NormalizedReelData
from app.services.ingestors.base import BaseIngestor


class InstagramIngestor(BaseIngestor):
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        super().__init__(timeout_seconds=timeout_seconds)

    async def ingest_reel(
        self,
        url: str,
        *,
        username: str | None = None,
        source_type: str = "competitor",
        force_refresh: bool = False,
        include_comments: bool = True,
        include_metrics: bool = True,
        cache_ttl_seconds: int = 1800,
        rate_limit_per_minute: int = 30,
    ) -> NormalizedReelData:
        canonical_url = self._canonical_url(url, username)
        cache_key = f"instagram:{canonical_url}"
        html = ""
        error: str | None = None
        try:
            html = await self.fetch_text(
                canonical_url,
                cache_key=cache_key,
                force_refresh=force_refresh,
                cache_ttl_seconds=cache_ttl_seconds,
                rate_limit_per_minute=rate_limit_per_minute,
            )
        except Exception as exc:
            error = str(exc)

        metadata = self._extract_metadata(html)
        caption = metadata.get("caption") or metadata.get("description") or ""
        transcript = metadata.get("transcript")
        audio_name = metadata.get("audio_name") or self._guess_audio_name(caption, metadata)
        hashtags = self._extract_hashtags(caption)
        posted_at = self._parse_datetime(metadata.get("published_time") or metadata.get("created_time"))
        comments = metadata.get("comments", []) if include_comments else []
        engagement = self._extract_engagement(metadata, caption) if include_metrics else ReelEngagementMetrics()
        hook_text = self._extract_hook_text(caption, transcript)
        posting_hour = posted_at.hour if posted_at else None

        normalized = NormalizedReelData(
            reel_id=self._build_id(canonical_url, username),
            source="instagram",
            source_type=source_type,
            username=username or metadata.get("username"),
            competitor_name=username or metadata.get("username"),
            reel_url=canonical_url,
            caption=caption,
            transcript=transcript,
            hook_text=hook_text,
            hook_type=self._classify_hook(hook_text, caption),
            audio_name=audio_name,
            hashtags=hashtags,
            comments=comments,
            comment_sentiment=self._sentiment_from_comments(comments),
            posted_at=posted_at,
            posting_hour=posting_hour,
            engagement=engagement,
            retention_signals=self._retention_signals(caption, transcript, hook_text, audio_name),
            visual_hooks=self._visual_hooks(caption, metadata),
            caption_patterns=self._caption_patterns(caption),
            trend_labels=self._trend_labels(caption, hashtags, audio_name),
            raw_metadata={**metadata, "fetch_error": error} if error else metadata,
            fetched_at=datetime.now(tz=UTC),
        )
        return normalized

    async def ingest_many(
        self,
        urls: list[str],
        *,
        usernames: list[str] | None = None,
        source_type: str = "competitor",
        force_refresh: bool = False,
        include_comments: bool = True,
        include_metrics: bool = True,
        cache_ttl_seconds: int = 1800,
        rate_limit_per_minute: int = 30,
        max_reels: int = 20,
    ) -> list[NormalizedReelData]:
        jobs: list[NormalizedReelData] = []
        usernames = usernames or []
        sources: list[tuple[str, str | None, str]] = []
        for reel_url in urls[:max_reels]:
            sources.append((reel_url, None, source_type))
        for username in usernames:
            profile_url = f"https://www.instagram.com/{username.strip().lstrip('@')}/reels/"
            sources.append((profile_url, username.strip().lstrip("@"), "competitor_profile"))

        for reel_url, username, item_source_type in sources[:max_reels]:
            jobs.append(
                await self.ingest_reel(
                    reel_url,
                    username=username,
                    source_type=item_source_type,
                    force_refresh=force_refresh,
                    include_comments=include_comments,
                    include_metrics=include_metrics,
                    cache_ttl_seconds=cache_ttl_seconds,
                    rate_limit_per_minute=rate_limit_per_minute,
                )
            )
        return jobs

    @staticmethod
    def _canonical_url(url: str, username: str | None) -> str:
        if url:
            return url.strip()
        if username:
            handle = username.strip().lstrip("@")
            return f"https://www.instagram.com/{handle}/reels/"
        return "https://www.instagram.com/"

    @staticmethod
    def _build_id(url: str, username: str | None) -> str:
        digest = hashlib.sha1(f"{url}|{username or ''}".encode("utf-8")).hexdigest()
        return f"reel-{digest[:16]}"

    @staticmethod
    def _extract_metadata(html: str) -> dict[str, Any]:
        if not html:
            return {}

        metadata: dict[str, Any] = {}

        def capture_meta(pattern: str, key: str) -> None:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                metadata[key] = unescape(match.group(1)).strip()

        capture_meta(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', "title")
        capture_meta(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', "description")
        capture_meta(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', "caption")
        capture_meta(r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']', "published_time")
        capture_meta(r'<meta[^>]+property=["\']instapp:hashtags["\'][^>]+content=["\']([^"\']+)["\']', "hashtags")

        ld_json = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
        for payload in ld_json:
            try:
                parsed = json.loads(unescape(payload.strip()))
            except Exception:
                continue
            if isinstance(parsed, dict):
                metadata.update(self._normalize_ld_json(parsed))
                break

        if "caption" not in metadata:
            fallback = re.search(r'"caption"\s*:\s*"([^"]+)"', html)
            if fallback:
                metadata["caption"] = unescape(fallback.group(1)).strip()

        metadata["comments"] = []
        return metadata

    @staticmethod
    def _normalize_ld_json(payload: dict[str, Any]) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if payload.get("headline"):
            metadata.setdefault("title", payload["headline"])
        if payload.get("description"):
            metadata.setdefault("caption", payload["description"])
        if payload.get("author"):
            author = payload.get("author")
            if isinstance(author, dict):
                metadata.setdefault("username", author.get("name"))
        if payload.get("uploadDate"):
            metadata.setdefault("published_time", payload["uploadDate"])
        if payload.get("keywords"):
            metadata["hashtags"] = payload["keywords"]
        return metadata

    @staticmethod
    def _extract_hashtags(caption: str) -> list[str]:
        return sorted({tag.lower() for tag in re.findall(r"#\w+", caption or "")})[:12]

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except Exception:
            return None

    @staticmethod
    def _guess_audio_name(caption: str, metadata: dict[str, Any]) -> str | None:
        for key in ("audio_name", "audio", "sound", "music"):
            value = metadata.get(key)
            if value:
                return str(value)
        if "audio" in (caption or "").lower():
            return "reel audio"
        return None

    @staticmethod
    def _extract_engagement(metadata: dict[str, Any], caption: str) -> ReelEngagementMetrics:
        text = json.dumps(metadata, ensure_ascii=True).lower() + " " + (caption or "").lower()
        numbers = [int(match.group(1).replace(",", "")) for match in re.finditer(r"(\d[\d,]*)", text)]
        views = numbers[0] if numbers else None
        likes = numbers[1] if len(numbers) > 1 else None
        comments = numbers[2] if len(numbers) > 2 else None
        shares = numbers[3] if len(numbers) > 3 else None
        saves = numbers[4] if len(numbers) > 4 else None
        engagement_rate = None
        if views and (likes or comments or shares or saves):
            engagement_rate = round(((likes or 0) + (comments or 0) + (shares or 0) + (saves or 0)) / max(1, views) * 100, 2)
        retention_proxy = None
        if caption:
            retention_proxy = min(100.0, max(0.0, 40.0 + min(30, len(caption.split()))))
        return ReelEngagementMetrics(
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            saves=saves,
            engagement_rate=engagement_rate,
            retention_proxy=retention_proxy,
        )

    @staticmethod
    def _extract_hook_text(caption: str, transcript: str | None) -> str | None:
        source = transcript or caption or ""
        if not source:
            return None
        words = source.split()
        return " ".join(words[:12]).strip() or None

    @staticmethod
    def _classify_hook(hook_text: str | None, caption: str) -> str | None:
        text = f"{hook_text or ''} {caption or ''}".lower()
        if any(token in text for token in ["why", "what if", "mistake", "secret", "stop"]):
            return "curiosity"
        if any(token in text for token in ["save", "learn", "grow", "faster"]):
            return "benefit_driven"
        if any(token in text for token in ["vs", "instead", "wrong"]):
            return "contrarian"
        if any(token in text for token in ["proof", "case study", "results"]):
            return "social_proof"
        return "opening"

    @staticmethod
    def _sentiment_from_comments(comments: list[str]) -> str | None:
        if not comments:
            return "unknown"
        text = " ".join(comments).lower()
        positive = sum(1 for token in ["love", "great", "wow", "yes", "amazing", "useful"] if token in text)
        negative = sum(1 for token in ["bad", "fake", "scam", "boring", "hate"] if token in text)
        if positive > negative:
            return "positive"
        if negative > positive:
            return "negative"
        return "neutral"

    @staticmethod
    def _retention_signals(caption: str, transcript: str | None, hook_text: str | None, audio_name: str | None) -> list[str]:
        signals: list[str] = []
        text = f"{caption or ''} {transcript or ''} {hook_text or ''}".lower()
        if any(token in text for token in ["why", "secret", "mistake", "stop", "what if"]):
            signals.append("curiosity_hook")
        if any(token in text for token in ["before", "after", "results", "proof", "case study"]):
            signals.append("proof_loop")
        if audio_name:
            signals.append("audio_anchor")
        if len((caption or "").split()) <= 20:
            signals.append("tight_caption")
        return signals or ["neutral_pacing"]

    @staticmethod
    def _visual_hooks(caption: str, metadata: dict[str, Any]) -> list[str]:
        hooks: list[str] = []
        text = f"{caption or ''} {metadata.get('description', '')}".lower()
        if any(token in text for token in ["before", "after", "split", "transformation"]):
            hooks.append("before_after_visual")
        if any(token in text for token in ["close-up", "zoom", "frame"]):
            hooks.append("camera_interrupt")
        if any(token in text for token in ["text", "caption", "overlay"]):
            hooks.append("text_overlay")
        return hooks or ["minimal_visual_hook"]

    @staticmethod
    def _caption_patterns(caption: str) -> list[str]:
        patterns: list[str] = []
        text = (caption or "").lower()
        if text.startswith("why "):
            patterns.append("question_open")
        if text.endswith("?"):
            patterns.append("question_close")
        if any(token in text for token in ["3 tips", "5 ways", "3 reasons"]):
            patterns.append("listicle")
        if any(token in text for token in ["save this", "share this", "comment"]):
            patterns.append("engagement_bait")
        return patterns or ["direct_caption"]

    @staticmethod
    def _trend_labels(caption: str, hashtags: list[str], audio_name: str | None) -> list[str]:
        labels = list(hashtags)
        if audio_name:
            labels.append(f"audio:{audio_name.lower()}")
        if "tutorial" in (caption or "").lower():
            labels.append("tutorial_format")
        if "story" in (caption or "").lower():
            labels.append("story_format")
        return labels[:12]
