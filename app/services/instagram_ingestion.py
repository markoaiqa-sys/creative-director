from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.models import (
    InstagramIngestionJob,
    InstagramIngestionRequest,
    InstagramIngestionResult,
    NormalizedReelData,
    ReelReference,
)
from app.services.ingestors.competitor_tracker import CompetitorTracker
from app.services.ingestors.instagram_ingestor import InstagramIngestor
from app.services.ingestors.trend_collector import TrendCollector


class InstagramIngestionService:
    def __init__(self, *, ingestor: InstagramIngestor, trend_collector: TrendCollector, competitor_tracker: CompetitorTracker, storage=None) -> None:
        self._ingestor = ingestor
        self._trend_collector = trend_collector
        self._competitor_tracker = competitor_tracker
        self._storage = storage
        self._jobs: dict[str, InstagramIngestionJob] = {}
        self._results: dict[str, InstagramIngestionResult] = {}
        self._job_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def submit(self, request: InstagramIngestionRequest) -> InstagramIngestionJob:
        job = InstagramIngestionJob(
            job_id=str(uuid4()),
            status="queued",
            message="queued",
            request=request,
            progress=0,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        async with self._lock:
            self._jobs[job.job_id] = job
            task = asyncio.create_task(self._run_job(job.job_id))
            self._job_tasks[job.job_id] = task
        if not request.async_job:
            await task
        return await self.get_job(job.job_id)

    async def get_job(self, job_id: str) -> InstagramIngestionJob:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            return job

    async def get_result(self, job_id: str) -> InstagramIngestionResult:
        async with self._lock:
            result = self._results.get(job_id)
            if result is None:
                raise KeyError(job_id)
            return result

    async def list_jobs(self) -> list[InstagramIngestionJob]:
        async with self._lock:
            return sorted(self._jobs.values(), key=lambda item: item.updated_at, reverse=True)

    async def _run_job(self, job_id: str) -> None:
        try:
            job = await self.get_job(job_id)
            await self._update_job(job_id, status="running", progress=5, message="initializing ingestion")
            request = job.request

            reels = await self._ingestor.ingest_many(
                request.reel_urls,
                usernames=request.instagram_usernames,
                force_refresh=request.force_refresh,
                include_comments=request.include_comments,
                include_metrics=request.include_metrics,
                cache_ttl_seconds=request.cache_ttl_seconds,
                rate_limit_per_minute=request.rate_limit_per_minute,
                max_reels=request.max_reels,
            )

            direct_reels = [*request.competitor_reels, *request.trending_reels]
            reels.extend(self._normalize_references(direct_reels))
            await self._update_job(job_id, progress=45, message=f"ingested {len(reels)} reels")

            previous_snapshots = self._storage.load_instagram_trend_snapshots() if self._storage and hasattr(self._storage, "load_instagram_trend_snapshots") else []
            snapshots, trend_objects, summary = self._trend_collector.collect(
                reels,
                niche=request.niche,
                audience=request.audience,
                previous_snapshots=previous_snapshots,
            )
            await self._update_job(job_id, progress=70, message="trend signals collected")

            competitor_insights, benchmark_score, top_patterns, content_gaps = self._competitor_tracker.benchmark(reels)
            await self._update_job(job_id, progress=85, message="competitor benchmarks computed")

            result = InstagramIngestionResult(
                reels=reels,
                trend_snapshots=snapshots,
                competitor_insights=competitor_insights,
                benchmark_score=benchmark_score,
                hook_library=summary["hook_library"],
                caption_patterns=summary["caption_patterns"],
                hashtag_patterns=summary["hashtag_patterns"],
                posting_time_patterns=summary["posting_time_patterns"],
                audio_patterns=summary["audio_patterns"],
                momentum_score=float(summary["momentum_score"]),
                stored_snapshot_ids=[snapshot.snapshot_id for snapshot in snapshots],
            )
            if self._storage:
                self._persist(result, snapshots, competitor_insights, reels)
            async with self._lock:
                self._results[job_id] = result
            await self._update_job(job_id, status="completed", progress=100, message="ingestion complete", result_count=len(reels), finished_at=datetime.now(tz=UTC))
        except Exception as exc:
            await self._update_job(job_id, status="failed", message="ingestion failed", error=str(exc), finished_at=datetime.now(tz=UTC))

    def _persist(self, result: InstagramIngestionResult, snapshots, competitor_insights, reels: list[NormalizedReelData]) -> None:
        try:
            if hasattr(self._storage, "save_instagram_trend_snapshots"):
                existing = self._storage.load_instagram_trend_snapshots()
                existing.extend([snapshot.model_dump(mode="json") for snapshot in snapshots])
                self._storage.save_instagram_trend_snapshots(existing[-200:])
            if hasattr(self._storage, "save_instagram_competitor_benchmarks"):
                existing = self._storage.load_instagram_competitor_benchmarks()
                existing.extend([insight.model_dump(mode="json") for insight in competitor_insights])
                self._storage.save_instagram_competitor_benchmarks(existing[-200:])
            if hasattr(self._storage, "save_instagram_reel_library"):
                existing = self._storage.load_instagram_reel_library()
                existing.extend([reel.model_dump(mode="json") for reel in reels])
                self._storage.save_instagram_reel_library(existing[-400:])
        except Exception:
            return

    @staticmethod
    def _normalize_references(references: list[ReelReference]) -> list[NormalizedReelData]:
        normalized: list[NormalizedReelData] = []
        for index, reference in enumerate(references, start=1):
            normalized.append(
                NormalizedReelData(
                    reel_id=f"reference-{index}-{uuid4().hex[:8]}",
                    source="instagram",
                    source_type="reference",
                    username=reference.username,
                    competitor_name=reference.username,
                    reel_url=reference.reel_url,
                    caption=reference.caption or "",
                    transcript=reference.transcript,
                    audio_name=reference.audio_name,
                    hashtags=[],
                    comments=reference.comments,
                    comment_sentiment="unknown",
                    engagement={
                        "views": reference.views,
                        "likes": reference.likes,
                        "comments": len(reference.comments),
                        "shares": reference.shares,
                        "saves": reference.saves,
                        "engagement_rate": None,
                        "retention_proxy": None,
                    },
                    retention_signals=[],
                    visual_hooks=[],
                    caption_patterns=[],
                    trend_labels=[],
                    raw_metadata={"source": "request_reference"},
                    fetched_at=datetime.now(tz=UTC),
                )
            )
        return normalized

    async def _update_job(self, job_id: str, **updates: Any) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            data = job.model_dump(mode="json")
            data.update(updates)
            data["updated_at"] = datetime.now(tz=UTC)
            self._jobs[job_id] = InstagramIngestionJob.model_validate(data)
