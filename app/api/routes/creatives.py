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


from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, UploadFile, File, Form

# ... (omitted but Header is imported)

@router.post("/generate-creatives", response_model=CampaignPackage)
async def generate_creatives(
    payload: CreativeInput,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
    x_client_email: str | None = Header(None),
    x_is_guest: str | None = Header(None),
) -> CampaignPackage:
    try:
        is_guest_bool = x_is_guest == "true"
        return await engine.generate_campaign(payload, client_email=x_client_email, is_guest=is_guest_bool)
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
    x_client_email: str | None = Header(None),
    x_is_guest: str | None = Header(None),
) -> CampaignPackage:
    try:
        is_guest_bool = x_is_guest == "true"
        package = await engine.score_and_package(
            payload=req.payload,
            hooks=req.hooks,
            angles=req.angles,
            ad_copies=req.ad_copies,
            visual_concepts=req.visual_concepts,
            generated_creatives=req.generated_creatives,
            client_email=x_client_email,
            is_guest=is_guest_bool,
        )
        # Automatically add generated final images to the Knowledge Base
        if package and package.creative_assets:
            for c in package.creative_assets:
                if c.rendered_ad and c.rendered_ad.image_path:
                    # image_path is usually like /output/campaign_slug/timestamp/file.png
                    rel_path = c.rendered_ad.image_path.lstrip("/")
                    if rel_path.startswith("output/"):
                        rel_path = rel_path[7:]
                    
                    local_path = engine._storage._output_root / rel_path
                    if local_path.exists():
                        try:
                            data = local_path.read_bytes()
                            engine._storage.save_kb_image_from_bytes(
                                filename=local_path.name,
                                data=data,
                                title=f"Generated: {c.headline or c.concept_id}",
                                tags=["generation"]
                            )
                        except Exception as e:
                            print(f"[WARN] Failed to save generated image to KB: {e}")
        return package
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
    tags: str | None = Form(None),
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
) -> dict:
    """Upload an image to the knowledge base."""
    try:
        data = await file.read()
        tags_list = [t.strip() for t in tags.split(",")] if tags else None
        entry = engine._storage.save_kb_image_from_bytes(file.filename, data, title=title, tags=tags_list)
        return entry
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/knowledge-base/images")
async def list_kb_images(
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
):
    return {"items": engine._storage.list_kb_images()}

@router.delete("/knowledge-base/images/{image_id}")
async def delete_kb_image(
    image_id: str,
    _actor: str = Depends(require_api_auth),
    engine: CreativeDirectorEngine = Depends(get_engine),
):
    success = engine._storage.delete_kb_image(image_id)
    if not success:
        raise HTTPException(status_code=404, detail="Image not found")
    return {"success": True}
