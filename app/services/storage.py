import json
import logging
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    boto3 = import_module("boto3")
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None

from app.core.config import Settings
from app.models import CampaignPackage, Platform, TopCreativeItem, TopCreativesResponse, CampaignHistoryItem, CampaignHistoryResponse


class CampaignStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._output_root = settings.output_root
        self._output_root.mkdir(parents=True, exist_ok=True)
        self._kb_root = self._output_root / "knowledge_base"
        self._kb_root.mkdir(parents=True, exist_ok=True)
        self._s3_bucket_name = settings.s3_bucket_name
        self._s3_client = (
            boto3.client("s3", region_name=settings.s3_region)
            if settings.s3_bucket_name and boto3 is not None
            else None
        )
        from app.core.supabase import DatabasePool
        self._pool = DatabasePool(settings)

    def save_package(self, package: CampaignPackage) -> str:
        campaign_dir = self.build_campaign_dir(package.campaign_slug, package.created_at)

        payloads = {
            "input.json": package.input.model_dump(mode="json"),
            "hooks.json": [item.model_dump(mode="json") for item in package.hooks],
            "angles.json": [item.model_dump(mode="json") for item in package.angles],
            "ad_copy.json": [item.model_dump(mode="json") for item in package.ad_copies],
            "visual_concepts.json": [item.model_dump(mode="json") for item in package.visual_concepts],
            "creative_scores.json": [item.model_dump(mode="json") for item in package.scored_creatives],
            "creatives.json": [item.model_dump(mode="json") for item in package.creative_assets],
            "export_rows.json": [item.model_dump(mode="json") for item in package.export_rows],
            "campaign_manifest.json": {
                "campaign_name": package.campaign_name,
                "campaign_slug": package.campaign_slug,
                "created_at": package.created_at.isoformat(),
                "platform": package.input.platform.value,
                "objective": package.input.objective.value,
                "brand_assets": package.brand_assets.model_dump(mode="json") if package.brand_assets else None,
                "output_directory": str(campaign_dir),
            },
        }

        for filename, payload in payloads.items():
            file_path = campaign_dir / filename
            self._write_json(file_path, payload)
            self._mirror_to_s3(file_path=file_path, relative_key=file_path.relative_to(self._output_root))

        self.sync_campaign_dir_to_db(campaign_dir)

        return str(campaign_dir)

    def build_campaign_dir(self, campaign_slug: str, created_at) -> Path:
        timestamp = created_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        campaign_dir = self._output_root / campaign_slug / timestamp
        campaign_dir.mkdir(parents=True, exist_ok=True)
        return campaign_dir

    def get_top_creatives(
        self,
        *,
        limit: int | None = None,
        platform: Platform | None = None,
    ) -> TopCreativesResponse:
        items: list[tuple[datetime, int, TopCreativeItem]] = []

        for creatives_file in self._output_root.glob("*/*/creatives.json"):
            try:
                rows = json.loads(creatives_file.read_text(encoding="utf-8"))
            except Exception:
                continue

            campaign_timestamp = self._extract_campaign_timestamp(creatives_file.parent.name)

            for row in rows:
                row_platform = row.get("platform")
                normalized_platform = self._parse_platform(row_platform)
                if platform and normalized_platform != platform:
                    continue
                score = row.get("score", {})
                generated = row.get("generated_creative", {})
                
                # Normalize paths to web-accessible URLs
                raw_rendered = (row.get("rendered_ad") or {}).get("image_path")
                raw_preview = (row.get("preview") or {}).get("image_path")
                item = TopCreativeItem(
                    campaign_name=row.get("campaign_name", creatives_file.parent.parent.name),
                    campaign_slug=row.get("campaign_slug", creatives_file.parent.parent.name),
                    platform=normalized_platform,
                    concept_id=row.get("concept_id", "unknown"),
                    total_score=score.get("total_score", 0),
                    primary_text=row.get("primary_text"),
                    headline=row.get("headline"),
                    description=row.get("description"),
                    cta=row.get("cta"),
                    image_urls=generated.get("image_urls", []),
                    video_urls=generated.get("video_urls", []),
                    rendered_image_path=self._normalize_web_path(raw_rendered),
                    preview_image_path=self._normalize_web_path(raw_preview),
                    output_directory=str(creatives_file.parent),
                )
                items.append((campaign_timestamp, score.get("total_score", 0), item))

        ranked = sorted(items, key=lambda entry: (entry[0], entry[1]), reverse=True)
        top_items = [entry[2] for entry in ranked]
        if limit is not None:
            top_items = top_items[:limit]
        return TopCreativesResponse(items=top_items)

    def _extract_campaign_timestamp(self, folder_name: str) -> datetime:
        try:
            return datetime.strptime(folder_name, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)

    def get_campaign_history(
        self,
        *,
        limit: int | None = None,
        platform: Platform | None = None,
    ) -> CampaignHistoryResponse:
        """Get campaign-level history grouped by campaign_slug with all creatives from all runs."""
        campaign_data: dict[str, dict] = {}

        # Find all campaign manifest files
        for manifest_file in self._output_root.glob("*/*/campaign_manifest.json"):
            campaign_dir = manifest_file.parent
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                campaign_slug = manifest.get("campaign_slug", campaign_dir.parent.name)
                timestamp_str = campaign_dir.name
                campaign_timestamp = self._extract_campaign_timestamp(timestamp_str)
                
                # Filter by platform if specified
                manifest_platform = self._parse_platform(manifest.get("platform"))
                if platform and manifest_platform != platform:
                    continue
                
                # Read hooks, angles, visuals, creatives from the campaign folder
                hooks = self._read_json_file(campaign_dir / "hooks.json", [])
                angles = self._read_json_file(campaign_dir / "angles.json", [])
                visual_concepts = self._read_json_file(campaign_dir / "visual_concepts.json", [])
                creatives = self._read_json_file(campaign_dir / "creatives.json", [])
                creative_scores = self._read_json_file(campaign_dir / "creative_scores.json", [])
                
                # Calculate top score
                top_score = max([c.get("total_score", 0) for c in creative_scores], default=0) if creative_scores else 0
                
                # Build creatives with rendered paths
                enriched_creatives = []
                for creative in creatives:
                    rendered_ad = creative.get("rendered_ad", {})
                    preview = creative.get("preview", {})
                    enriched_creatives.append({
                        "concept_id": creative.get("concept_id"),
                        "primary_text": creative.get("primary_text"),
                        "headline": creative.get("headline"),
                        "description": creative.get("description"),
                        "cta": creative.get("cta"),
                        "score": next((c for c in creative_scores if c.get("concept_id") == creative.get("concept_id")), {}).get("total_score", 0),
                        "rendered_image_path": self._normalize_web_path(rendered_ad.get("image_path")) if rendered_ad else None,
                        "preview_image_path": self._normalize_web_path(preview.get("image_path")) if preview else None,
                    })
                
                # If this campaign_slug already exists, merge creatives
                if campaign_slug in campaign_data:
                    existing = campaign_data[campaign_slug]
                    # Merge creatives (avoid duplicates by concept_id)
                    existing_concept_ids = {c["concept_id"] for c in existing["creatives"]}
                    new_creatives = [c for c in enriched_creatives if c["concept_id"] not in existing_concept_ids]
                    existing["creatives"].extend(new_creatives)
                    # Update to highest score
                    if top_score > existing["top_score"]:
                        existing["top_score"] = top_score
                    # Update to most recent timestamp
                    if campaign_timestamp > existing["timestamp"]:
                        existing["timestamp"] = campaign_timestamp
                        existing["created_at"] = manifest.get("created_at", timestamp_str)
                else:
                    campaign_data[campaign_slug] = {
                        "campaign_name": manifest.get("campaign_name", campaign_slug),
                        "campaign_slug": campaign_slug,
                        "created_at": manifest.get("created_at", timestamp_str),
                        "timestamp": campaign_timestamp,
                        "platform": manifest_platform,
                        "objective": manifest.get("objective", "unknown"),
                        "top_score": top_score,
                        "hooks": hooks,
                        "angles": angles,
                        "visual_concepts": visual_concepts,
                        "creatives": enriched_creatives,
                        "output_directory": str(campaign_dir),
                    }
            except Exception:
                continue
        
        # Convert to CampaignHistoryItem models and sort by top score
        items = [
            CampaignHistoryItem(
                campaign_name=data["campaign_name"],
                campaign_slug=data["campaign_slug"],
                created_at=data["created_at"],
                platform=data["platform"],
                objective=data["objective"],
                top_score=data["top_score"],
                total_creatives=len(data["creatives"]),
                hooks=data["hooks"],
                angles=data["angles"],
                visual_concepts=data["visual_concepts"],
                creatives=data["creatives"],
                output_directory=data["output_directory"],
            )
            for data in sorted(campaign_data.values(), key=lambda x: x["top_score"], reverse=True)
        ]
        
        if limit is not None:
            items = items[:limit]
        
        return CampaignHistoryResponse(items=items)

    def _read_json_file(self, file_path: Path, default: Any = None) -> Any:
        """Safely read a JSON file, returning default if it doesn't exist."""
        try:
            if file_path.exists():
                return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default if default is not None else []


    def _normalize_web_path(self, path_str: str | None) -> str | None:
        if not path_str:
            return None
        try:
            path = Path(path_str)
            if path.is_relative_to(self._output_root):
                return f"/output/{path.relative_to(self._output_root).as_posix()}"
        except Exception:
            pass
        return path_str

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def _mirror_to_s3(self, *, file_path: Path, relative_key: Path) -> None:
        if not self._s3_client or not self._s3_bucket_name:
            return
        self._s3_client.upload_file(str(file_path), self._s3_bucket_name, relative_key.as_posix())

    @staticmethod
    def _parse_platform(value: Any) -> Platform:
        if isinstance(value, Platform):
            return value
        if isinstance(value, str):
            try:
                return Platform(value)
            except ValueError:
                pass
        return Platform.META

    # Knowledge base helpers
    def save_kb_image_from_bytes(self, filename: str, data: bytes, title: str | None = None, tags: list[str] | None = None) -> dict:
        """Save a knowledge-base image and record metadata, with duplicate detection."""
        from hashlib import sha256
        
        # Calculate content hash to detect duplicates
        content_hash = sha256(data).hexdigest()
        
        # Check if image with same content already exists
        meta_path = self._kb_root / "metadata.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = []
        
        # Look for existing entry with same content hash
        for existing_entry in meta:
            if existing_entry.get("content_hash") == content_hash:
                # Update title and tags if provided and different
                if title and title != existing_entry.get("title"):
                    existing_entry["title"] = title
                if tags and tags != existing_entry.get("tags"):
                    existing_entry["tags"] = tags
                    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                return existing_entry
        
        # New image - save it
        ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        safe_name = f"{ts}-{filename}".replace(" ", "_")
        path = self._kb_root / safe_name
        path.write_bytes(data)

        web_path = f"/output/{path.relative_to(self._output_root).as_posix()}"

        entry = {
            "id": content_hash,
            "content_hash": content_hash,
            "title": title or filename,
            "filename": safe_name,
            "web_path": web_path,
            "tags": tags or [],
            "created_at": ts,
        }
        meta.insert(0, entry)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # mirror to s3 if configured
        try:
            self._mirror_to_s3(file_path=path, relative_key=path.relative_to(self._output_root))
        except Exception:
            pass

        # Sync to DB
        try:
            rel_path = path.relative_to(self._output_root).as_posix()
            mime = "image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "image/png"
            self.save_file_to_db(rel_path, data, mime)
        except Exception as e:
            logger.error(f"Failed to sync KB image to DB: {e}")

        return entry

    def list_kb_images(self) -> list[dict]:
        meta_path = self._kb_root / "metadata.json"
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def delete_kb_image(self, image_id: str) -> bool:
        meta_path = self._kb_root / "metadata.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return False
            
        updated_meta = []
        found = False
        for entry in meta:
            if entry.get("id") == image_id:
                found = True
                filename = entry.get("filename")
                if filename:
                    file_path = self._kb_root / filename
                    if file_path.exists():
                        try:
                            file_path.unlink()
                        except Exception as e:
                            logger.error(f"Failed to delete kb image {file_path}: {e}")
                    # Delete from DB
                    try:
                        rel_path = file_path.relative_to(self._output_root).as_posix()
                        self.delete_file_from_db(rel_path)
                    except Exception as e:
                        logger.error(f"Failed to delete KB image from DB: {e}")
            else:
                updated_meta.append(entry)
                
        if found:
            meta_path.write_text(json.dumps(updated_meta, indent=2), encoding="utf-8")
        return found

    def save_file_to_db(self, relative_path: str, data: bytes, content_type: str | None = None) -> None:
        if not self._pool.enabled:
            return
        rel_path = Path(relative_path).as_posix()
        from hashlib import md5
        file_id = md5(rel_path.encode("utf-8")).hexdigest()
        
        with self._pool.connection() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                try:
                    import psycopg2
                    cur.execute(
                        """
                        INSERT INTO stored_files (id, file_path, content_type, data)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (file_path) DO UPDATE 
                        SET data = EXCLUDED.data, content_type = EXCLUDED.content_type;
                        """,
                        (file_id, rel_path, content_type, psycopg2.Binary(data))
                    )
                except Exception as e:
                    logger.error(f"Failed to save file {rel_path} to DB: {e}")

    def delete_file_from_db(self, relative_path: str) -> None:
        if not self._pool.enabled:
            return
        rel_path = Path(relative_path).as_posix()
        with self._pool.connection() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                try:
                    cur.execute("DELETE FROM stored_files WHERE file_path = %s", (rel_path,))
                except Exception as e:
                    logger.error(f"Failed to delete file {rel_path} from DB: {e}")

    def sync_campaign_dir_to_db(self, campaign_dir: Path) -> None:
        if not self._pool.enabled:
            return
        import mimetypes
        for p in campaign_dir.rglob("*"):
            if p.is_file():
                try:
                    data = p.read_bytes()
                    rel_path = p.relative_to(self._output_root).as_posix()
                    mime, _ = mimetypes.guess_type(str(p))
                    self.save_file_to_db(rel_path, data, mime)
                except Exception as e:
                    logger.error(f"Failed to sync file {p} to DB: {e}")
