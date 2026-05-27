from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.auth import require_api_auth
from app.models import (
    InstagramAnalyzeCompetitorRequest,
    InstagramAnalyzeReelRequest,
    InstagramDetectTrendsRequest,
    InstagramDirectReelRequest,
    InstagramIngestionJob,
    InstagramIngestionRequest,
    InstagramIngestionResult,
    InstagramGenerateScriptRequest,
    InstagramReelsResponse,
    InstagramScoreReelRequest,
)
from app.services.engine import ServiceContainer
from app.services.instagram_ingestion import InstagramIngestionService
from app.services.instagram_engine import InstagramDirectorEngine

router = APIRouter(tags=["instagram"])


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def get_instagram_engine(container: ServiceContainer = Depends(get_container)) -> InstagramDirectorEngine:
    return container.instagram_engine


def get_ingestion_service(container: ServiceContainer = Depends(get_container)) -> InstagramIngestionService:
    return container.instagram_ingestion


@router.post("/instagram/analyze-reel", response_model=InstagramReelsResponse)
async def analyze_reel(
    payload: InstagramAnalyzeReelRequest,
    _actor: str = Depends(require_api_auth),
    engine: InstagramDirectorEngine = Depends(get_instagram_engine),
) -> InstagramReelsResponse:
    return await engine.analyze_reel(payload)


@router.post("/instagram/analyze-competitor", response_model=InstagramReelsResponse)
async def analyze_competitor(
    payload: InstagramAnalyzeCompetitorRequest,
    _actor: str = Depends(require_api_auth),
    engine: InstagramDirectorEngine = Depends(get_instagram_engine),
) -> InstagramReelsResponse:
    return await engine.analyze_competitor(payload)


@router.post("/instagram/detect-trends", response_model=InstagramReelsResponse)
async def detect_trends(
    payload: InstagramDetectTrendsRequest,
    _actor: str = Depends(require_api_auth),
    engine: InstagramDirectorEngine = Depends(get_instagram_engine),
) -> InstagramReelsResponse:
    return await engine.detect_trends(payload)


@router.post("/instagram/generate-script", response_model=InstagramReelsResponse)
async def generate_script(
    payload: InstagramGenerateScriptRequest,
    _actor: str = Depends(require_api_auth),
    engine: InstagramDirectorEngine = Depends(get_instagram_engine),
) -> InstagramReelsResponse:
    return await engine.generate_script(payload)


@router.post("/instagram/direct-reel", response_model=InstagramReelsResponse)
async def direct_reel(
    payload: InstagramDirectReelRequest,
    _actor: str = Depends(require_api_auth),
    engine: InstagramDirectorEngine = Depends(get_instagram_engine),
) -> InstagramReelsResponse:
    return await engine.direct_reel(payload)


@router.post("/instagram/score-reel", response_model=InstagramReelsResponse)
async def score_reel(
    payload: InstagramScoreReelRequest,
    _actor: str = Depends(require_api_auth),
    engine: InstagramDirectorEngine = Depends(get_instagram_engine),
) -> InstagramReelsResponse:
    return await engine.score_reel(payload)


@router.post("/instagram/ingest-reels", response_model=InstagramIngestionJob)
async def ingest_reels(
    payload: InstagramIngestionRequest,
    _actor: str = Depends(require_api_auth),
    service: InstagramIngestionService = Depends(get_ingestion_service),
) -> InstagramIngestionJob:
    return await service.submit(payload)


@router.get("/instagram/ingestion-jobs/{job_id}", response_model=InstagramIngestionJob)
async def get_ingestion_job(
    job_id: str,
    _actor: str = Depends(require_api_auth),
    service: InstagramIngestionService = Depends(get_ingestion_service),
) -> InstagramIngestionJob:
    try:
        return await service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ingestion job not found") from exc


@router.get("/instagram/ingestion-jobs/{job_id}/result", response_model=InstagramIngestionResult)
async def get_ingestion_result(
    job_id: str,
    _actor: str = Depends(require_api_auth),
    service: InstagramIngestionService = Depends(get_ingestion_service),
) -> InstagramIngestionResult:
    try:
        return await service.get_result(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ingestion result not available") from exc


@router.get("/instagram/trend-history")
async def get_trend_history(
    _actor: str = Depends(require_api_auth),
    container: ServiceContainer = Depends(get_container),
):
    storage = container.engine._storage
    if storage and hasattr(storage, "load_instagram_trend_snapshots"):
        return {"items": storage.load_instagram_trend_snapshots()}
    return {"items": []}


@router.get("/instagram/competitor-benchmarks")
async def get_competitor_benchmarks(
    _actor: str = Depends(require_api_auth),
    container: ServiceContainer = Depends(get_container),
):
    storage = container.engine._storage
    if storage and hasattr(storage, "load_instagram_competitor_benchmarks"):
        return {"items": storage.load_instagram_competitor_benchmarks()}
    return {"items": []}


@router.get("/instagram/reel-library")
async def get_reel_library(
    _actor: str = Depends(require_api_auth),
    container: ServiceContainer = Depends(get_container),
):
    storage = container.engine._storage
    if storage and hasattr(storage, "load_instagram_reel_library"):
        return {"items": storage.load_instagram_reel_library()}
    return {"items": []}