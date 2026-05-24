from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form

from app.api.auth import require_api_auth
from app.models import (
    CampaignPackage, 
    CreativeInput, 
    Platform, 
    TopCreativesResponse, 
    CampaignHistoryResponse,
    ConceptGenerationResponse,
    ImageGenerationRequest,
    ScoringRequest,
    GeneratedCreative,
)
from app.services.engine import CreativeDirectorEngine, ServiceContainer

router = APIRouter(tags=["creatives"])


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def get_engine(container: ServiceContainer = Depends(get_container)) -> CreativeDirectorEngine:
    return container.engine


@router.post("/generate-creatives", response_model=CampaignPackage)
async def generate_creatives(
    payload: CreativeInput,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> CampaignPackage:
    try:
        return await engine.generate_campaign(payload)
    except ValueError as exc:
        print(f"[ERROR] ValueError: {exc}")  # Add
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        print(f"[ERROR] RuntimeError: {exc}")  # Add
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # Add whole block
        print(f"[ERROR] Unexpected: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate-concepts", response_model=ConceptGenerationResponse)
async def api_generate_concepts(
    payload: CreativeInput,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> ConceptGenerationResponse:
    try:
        return await engine.generate_concepts(payload)
    except Exception as exc:
        print(f"[ERROR] generate_concepts failed: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/generate-image", response_model=GeneratedCreative)
async def api_generate_image(
    req: ImageGenerationRequest,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> GeneratedCreative:
    try:
        return await engine.generate_single_image(req.payload, req.concept)
    except Exception as exc:
        print(f"[ERROR] generate_image failed: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/score-and-package", response_model=CampaignPackage)
async def api_score_and_package(
    req: ScoringRequest,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> CampaignPackage:
    try:
        return await engine.score_and_package(
            payload=req.payload,
            hooks=req.hooks,
            angles=req.angles,
            ad_copies=req.ad_copies,
            visual_concepts=req.visual_concepts,
            generated_creatives=req.generated_creatives,
        )
    except Exception as exc:
        print(f"[ERROR] score_and_package failed: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/top-creatives", response_model=TopCreativesResponse)
async def get_top_creatives(
    limit: int | None = Query(default=None, ge=1, le=500),
    platform: Platform | None = None,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> TopCreativesResponse:
    return engine.get_top_creatives(limit=limit, platform=platform)


@router.get("/campaign-history", response_model=CampaignHistoryResponse)
async def get_campaign_history(
    limit: int | None = Query(default=None, ge=1, le=500),
    platform: Platform | None = None,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> CampaignHistoryResponse:
    return engine.get_campaign_history(limit=limit, platform=platform)


@router.post("/knowledge-base/images")
async def upload_kb_image(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> dict:
    """Upload an image to the knowledge base."""
    try:
        data = await file.read()
        entry = engine._storage.save_kb_image_from_bytes(file.filename, data, title=title)
        return entry
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/knowledge-base/images")
async def list_kb_images(
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
):
    return {"items": engine._storage.list_kb_images()}
