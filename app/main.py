from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import json
import mimetypes

from app.api.routes.creatives import router as creatives_router
from app.api.routes.chat import router as chat_router
from app.api.routes.instagram import router as instagram_router
from app.api.routes.suggestions import router as suggestions_router
from app.api.routes.providers import router as providers_router
from app.api.routes.auth import router as auth_router
from app.core.config import get_settings
from app.services.engine import ServiceContainer

# ---------------------------------------------------------------------------
# Load .env into os.environ so GOOGLE_CREDENTIALS_JSON (and other vars) are
# visible to os.getenv().  pydantic-settings loads them into its own Settings
# model but does NOT inject them into os.environ.
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass  # dotenv not installed; rely on actual environment

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CREDS_PATH = str(PROJECT_ROOT / "google-credentials.json")

# Write Google credentials from environment variable if present
google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if google_creds_json:
    try:
        # Parse and validate JSON
        creds_dict = json.loads(google_creds_json)
        with open(_CREDS_PATH, "w") as f:
            json.dump(creds_dict, f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _CREDS_PATH
        print(f"[INFO] Google credentials written to {_CREDS_PATH}")
    except Exception as e:
        print(f"[WARNING] Failed to write Google credentials: {e}")
elif Path(_CREDS_PATH).exists():
    # Credentials file already exists (e.g. created manually); just point the SDK at it.
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", _CREDS_PATH)
    print(f"[INFO] Using existing Google credentials at {_CREDS_PATH}")

FRONTEND_DIR = PROJECT_ROOT / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    container = ServiceContainer(settings)
    app.state.container = container
    yield
    await container.aclose()

settings = get_settings()
settings.output_root.mkdir(parents=True, exist_ok=True)
allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if settings.frontend_url and settings.frontend_url not in allowed_origins:
    allowed_origins.append(settings.frontend_url)
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(creatives_router)
app.include_router(chat_router)
app.include_router(instagram_router)
app.include_router(suggestions_router)
app.include_router(providers_router)
app.include_router(auth_router)
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

@app.get("/output/{file_path:path}")
async def serve_output_file(file_path: str):
    settings = get_settings()
    # Normalize path separator
    safe_path = file_path.replace("\\", "/")
    local_path = settings.output_root / safe_path
    
    if local_path.exists() and local_path.is_file():
        mime, _ = mimetypes.guess_type(str(local_path))
        return FileResponse(local_path, media_type=mime)
        
    # Fallback to Supabase Database
    from app.core.supabase import DatabasePool
    pool = DatabasePool(settings)
    if pool.enabled:
        with pool.connection() as conn:
            if conn is not None:
                with conn.cursor() as cur:
                    try:
                        cur.execute(
                            """
                            CREATE TABLE IF NOT EXISTS stored_files (
                                id VARCHAR(255) PRIMARY KEY,
                                file_path TEXT UNIQUE,
                                content_type VARCHAR(100),
                                data BYTEA,
                                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                            );
                            """
                        )
                        cur.execute(
                            "SELECT data, content_type FROM stored_files WHERE file_path = %s",
                            (safe_path,)
                        )
                        row = cur.fetchone()
                        if row:
                            data, content_type = row
                            
                            # Cache file locally so subsequent serves are fast
                            try:
                                local_path.parent.mkdir(parents=True, exist_ok=True)
                                local_path.write_bytes(bytes(data))
                            except Exception as e:
                                print(f"[INFO] Failed to cache file locally: {e}")
                                
                            return Response(content=bytes(data), media_type=content_type or "application/octet-stream")
                    except Exception as db_err:
                        print(f"[INFO] Database file serve error: {db_err}")
                        
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/styles.css", include_in_schema=False)
async def frontend_styles() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
async def frontend_app() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")


@app.get("/env-config.js", include_in_schema=False)
async def frontend_config() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "env-config.js", media_type="application/javascript")


@app.get("/IMG_20260420_033023.png", include_in_schema=False)
async def frontend_logo() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "IMG_20260420_033023.png", media_type="image/png")


@app.get("/icon1-removebg-preview.png", include_in_schema=False)
async def frontend_icon() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "icon1-removebg-preview.png", media_type="image/png")

@app.get("/")
async def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/ui-config")
async def ui_config() -> dict[str, str]:
    return {
        "app_name": settings.app_name,
        "backend_url": settings.backend_url,
        "frontend_url": settings.frontend_url,
        "groq_status": "Connected" if settings.groq_api_key else "Missing key",
        "nanobanana_status": "Configured" if settings.nanobanana_api_key else "Unavailable",
        "google_client_id": settings.google_client_id or "",
    }

@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
