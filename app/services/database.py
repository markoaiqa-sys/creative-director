import json
import logging
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from app.core.config import Settings
from app.core.supabase import DatabasePool
from app.models import (
    CampaignPackage,
    Platform,
    TopCreativeItem,
    TopCreativesResponse,
    CampaignHistoryItem,
    CampaignHistoryResponse,
)

logger = logging.getLogger(__name__)


class BaseDatabase:
    def __init__(self, settings: Settings) -> None:
        self._pool = DatabasePool(settings)

    @contextmanager
    def _cursor(self) -> Generator:
        with self._pool.connection() as conn:
            if conn is None:
                yield None
                return
            with conn.cursor() as cur:
                yield cur

    def close(self) -> None:
        self._pool.close()


class ChatDatabase(BaseDatabase):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._init_db()

    def _init_db(self) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            # Do not drop tables to preserve data!
            
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id VARCHAR(255) PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                );
                """
            )
            
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id VARCHAR(255),
                    file_name TEXT NOT NULL,
                    file_type VARCHAR(50),
                    file_path TEXT,
                    file_content TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                );
                """
            )
            
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id VARCHAR(255),
                    campaign_name TEXT,
                    execution_type VARCHAR(100),
                    input_data JSONB,
                    output_data JSONB,
                    status VARCHAR(50),
                    error_message TEXT,
                    execution_time_ms INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            
            # Drop foreign key if it previously existed so we can save anonymous sessions
            try:
                cur.execute(
                    """
                    ALTER TABLE execution_history
                    DROP CONSTRAINT IF EXISTS execution_history_session_id_fkey;
                    """
                )
            except Exception as e:
                logger.warning(f"Failed to drop constraint (might not exist): {e}")
            
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
                """
            )
            
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_base_session_id ON knowledge_base(session_id);
                """
            )
            
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_execution_history_session_id ON execution_history(session_id);
                """
            )

    def save_message(self, session_id: str, role: str, content: str) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            cur.execute("SELECT id FROM chat_sessions WHERE id = %s", (session_id,))
            if not cur.fetchone():
                title = content[:30] + ("..." if len(content) > 30 else "") if role == "user" else "Creative Assistant Chat"
                cur.execute("INSERT INTO chat_sessions (id, title) VALUES (%s, %s);", (session_id, title))
            cur.execute(
                """
                INSERT INTO chat_messages (id, session_id, role, content)
                VALUES (%s, %s, %s, %s);
                """,
                (str(uuid.uuid4()), session_id, role, content),
            )

    def get_history(self, session_id: str) -> list[dict]:
        with self._cursor() as cur:
            if cur is None:
                return []
            cur.execute(
                """
                SELECT role, content FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC;
                """,
                (session_id,),
            )
            return [{"role": row[0], "content": row[1]} for row in cur.fetchall()]

    def get_sessions(self) -> list[dict]:
        with self._cursor() as cur:
            if cur is None:
                return []
            cur.execute(
                """
                SELECT m.session_id, max(m.created_at) as last_activity, s.title
                FROM chat_messages m
                LEFT JOIN chat_sessions s ON m.session_id = s.id
                GROUP BY m.session_id, s.title
                ORDER BY last_activity DESC
                LIMIT 20;
                """
            )
            return [{"session_id": row[0], "last_activity": row[1].isoformat(), "title": row[2]} for row in cur.fetchall()]

    def save_knowledge_base_item(self, session_id: str, file_name: str, file_type: str, file_path: str, 
                                 file_content: str | None = None, metadata: dict | None = None) -> str | None:
        """Save a knowledge base item to Supabase."""
        with self._cursor() as cur:
            if cur is None:
                return None
            try:
                cur.execute(
                    """
                    INSERT INTO knowledge_base (session_id, file_name, file_type, file_path, file_content, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (session_id, file_name, file_type, file_path, file_content, json.dumps(metadata or {})),
                )
                result = cur.fetchone()
                return str(result[0]) if result else None
            except Exception as exc:
                logger.exception("Error saving knowledge base item: %s", exc)
                return None

    def get_knowledge_base(self, session_id: str) -> list[dict]:
        """Retrieve all knowledge base items for a session."""
        with self._cursor() as cur:
            if cur is None:
                return []
            try:
                cur.execute(
                    """
                    SELECT id, file_name, file_type, file_path, metadata, created_at
                    FROM knowledge_base
                    WHERE session_id = %s
                    ORDER BY created_at DESC;
                    """,
                    (session_id,),
                )
                results = []
                for row in cur.fetchall():
                    results.append({
                        "id": str(row[0]),
                        "file_name": row[1],
                        "file_type": row[2],
                        "file_path": row[3],
                        "metadata": json.loads(row[4]) if row[4] else {},
                        "created_at": row[5].isoformat() if row[5] else None,
                    })
                return results
            except Exception as exc:
                logger.exception("Error retrieving knowledge base: %s", exc)
                return []

    def save_execution_history(self, session_id: str, campaign_name: str, execution_type: str, 
                              input_data: dict, output_data: dict | None = None, status: str = "success",
                              error_message: str | None = None, execution_time_ms: int = 0) -> str | None:
        """Save execution/generation history to Supabase."""
        with self._cursor() as cur:
            if cur is None:
                return None
            try:
                cur.execute(
                    """
                    INSERT INTO execution_history (session_id, campaign_name, execution_type, input_data, 
                                                    output_data, status, error_message, execution_time_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (session_id, campaign_name, execution_type, json.dumps(input_data), 
                     json.dumps(output_data or {}), status, error_message, execution_time_ms),
                )
                result = cur.fetchone()
                return str(result[0]) if result else None
            except Exception as exc:
                logger.exception("Error saving execution history: %s", exc)
                return None

    def get_execution_history(self, session_id: str, limit: int = 50) -> list[dict]:
        """Retrieve execution history for a session."""
        with self._cursor() as cur:
            if cur is None:
                return []
            try:
                cur.execute(
                    """
                    SELECT id, campaign_name, execution_type, input_data, output_data, status, 
                           error_message, execution_time_ms, created_at
                    FROM execution_history
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (session_id, limit),
                )
                results = []
                for row in cur.fetchall():
                    results.append({
                        "id": str(row[0]),
                        "campaign_name": row[1],
                        "execution_type": row[2],
                        "input_data": json.loads(row[3]) if row[3] else {},
                        "output_data": json.loads(row[4]) if row[4] else {},
                        "status": row[5],
                        "error_message": row[6],
                        "execution_time_ms": row[7],
                        "created_at": row[8].isoformat() if row[8] else None,
                    })
                return results
            except Exception as exc:
                logger.exception("Error retrieving execution history: %s", exc)
                return []


class CampaignDatabase(BaseDatabase):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._init_db()

    def _init_db(self) -> None:
        with self._cursor() as cur:
            if cur is None:
                return
            # Create creative_campaigns table if it doesn't exist
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS creative_campaigns (
                    id SERIAL PRIMARY KEY,
                    campaign_name TEXT NOT NULL,
                    campaign_slug TEXT,
                    brand_name TEXT,
                    platform VARCHAR(50),
                    objective VARCHAR(100),
                    input_data JSONB,
                    hooks JSONB,
                    angles JSONB,
                    ad_copies JSONB,
                    visual_concepts JSONB,
                    generated_creatives JSONB,
                    scored_creatives JSONB,
                    creative_assets JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Create index if it doesn't exist
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_creative_campaigns_slug ON creative_campaigns(campaign_slug);
                """
            )

    def save_campaign(self, package: CampaignPackage) -> str | None:
        with self._cursor() as cur:
            if cur is None:
                return None
            try:
                cur.execute(
                    """
                    INSERT INTO creative_campaigns (
                        campaign_name, campaign_slug, brand_name, platform, objective,
                        input_data, hooks, angles, ad_copies, visual_concepts,
                        generated_creatives, scored_creatives, creative_assets
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id;
                    """,
                    (
                        package.campaign_name,
                        package.campaign_slug,
                        package.input.brand_name,
                        package.input.platform.value,
                        package.input.objective.value,
                        json.dumps(package.input.model_dump(mode="json")),
                        json.dumps([h.model_dump(mode="json") for h in package.hooks]),
                        json.dumps([a.model_dump(mode="json") for a in package.angles]),
                        json.dumps([c.model_dump(mode="json") for c in package.ad_copies]),
                        json.dumps([v.model_dump(mode="json") for v in package.visual_concepts]),
                        json.dumps([g.model_dump(mode="json") for g in package.generated_creatives]),
                        json.dumps([s.model_dump(mode="json") for s in package.scored_creatives]),
                        json.dumps([a.model_dump(mode="json") for a in package.creative_assets]),
                    ),
                )
                result = cur.fetchone()
                return result[0] if result else None
            except Exception as exc:
                logger.exception("Database save error: %s", exc)
                return None

    def get_campaigns(self, limit: int = 20) -> list[dict]:
        with self._cursor() as cur:
            if cur is None:
                return []
            try:
                cur.execute(
                    """
                    SELECT id, campaign_name, campaign_slug, brand_name, platform, objective, created_at
                    FROM creative_campaigns
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                columns = [desc[0] for desc in cur.description]
                results = []
                for row in cur.fetchall():
                    item = dict(zip(columns, row))
                    if item.get("created_at"):
                        item["created_at"] = item["created_at"].isoformat()
                    results.append(item)
                return results
            except Exception as exc:
                logger.exception("Database fetch error: %s", exc)
                return []

    def get_campaign_history(self, limit: int | None = None, platform: Platform | None = None) -> CampaignHistoryResponse:
        with self._cursor() as cur:
            if cur is None:
                return CampaignHistoryResponse(items=[])
            
            try:
                query = """
                    SELECT campaign_name, campaign_slug, platform, objective, created_at,
                           hooks, angles, visual_concepts, creative_assets
                    FROM creative_campaigns
                """
                params = []
                if platform:
                    query += " WHERE platform = %s "
                    params.append(platform.value)
                query += " ORDER BY created_at DESC "
                
                cur.execute(query, tuple(params))
                
                campaign_data: dict[str, dict] = {}
                for row in cur.fetchall():
                    c_name, c_slug, c_plat, c_obj, c_created, hooks_str, angles_str, concepts_str, assets_str = row
                    if not c_slug: continue
                    
                    # psycopg2 automatically deserializes JSONB
                    hooks = hooks_str if isinstance(hooks_str, list) else (json.loads(hooks_str) if hooks_str else [])
                    angles = angles_str if isinstance(angles_str, list) else (json.loads(angles_str) if angles_str else [])
                    concepts = concepts_str if isinstance(concepts_str, list) else (json.loads(concepts_str) if concepts_str else [])
                    assets = assets_str if isinstance(assets_str, list) else (json.loads(assets_str) if assets_str else [])
                    
                    creatives = []
                    top_score = 0
                    for asset in assets:
                        score = asset.get("score", {}).get("total_score", 0)
                        if score > top_score:
                            top_score = score
                        
                        rendered_ad = asset.get("rendered_ad") or {}
                        preview = asset.get("preview") or {}
                        
                        creatives.append({
                            "concept_id": asset.get("concept_id"),
                            "primary_text": asset.get("primary_text"),
                            "headline": asset.get("headline"),
                            "description": asset.get("description"),
                            "cta": asset.get("cta"),
                            "score": score,
                            "rendered_image_path": rendered_ad.get("image_base64") or rendered_ad.get("image_path"),
                            "preview_image_path": preview.get("image_base64") or preview.get("image_path"),
                        })
                    
                    if c_slug in campaign_data:
                        existing = campaign_data[c_slug]
                        existing_concept_ids = {c["concept_id"] for c in existing["creatives"]}
                        new_creatives = [c for c in creatives if c["concept_id"] not in existing_concept_ids]
                        existing["creatives"].extend(new_creatives)
                        if top_score > existing["top_score"]:
                            existing["top_score"] = top_score
                    else:
                        campaign_data[c_slug] = {
                            "campaign_name": c_name,
                            "campaign_slug": c_slug,
                            "created_at": c_created.isoformat() if c_created else "",
                            "platform": c_plat,
                            "objective": c_obj,
                            "top_score": top_score,
                            "hooks": hooks,
                            "angles": angles,
                            "visual_concepts": concepts,
                            "creatives": creatives,
                            "output_directory": "",
                        }
                
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
            except Exception as exc:
                logger.exception("Database fetch error: %s", exc)
                return CampaignHistoryResponse(items=[])

    def get_top_creatives(self, limit: int | None = None, platform: Platform | None = None) -> TopCreativesResponse:
        with self._cursor() as cur:
            if cur is None:
                return TopCreativesResponse(items=[])
            
            try:
                query = "SELECT campaign_name, campaign_slug, platform, creative_assets FROM creative_campaigns"
                params = []
                if platform:
                    query += " WHERE platform = %s "
                    params.append(platform.value)
                
                cur.execute(query, tuple(params))
                
                all_creatives = []
                for row in cur.fetchall():
                    c_name, c_slug, c_plat, assets_str = row
                    assets = assets_str if isinstance(assets_str, list) else (json.loads(assets_str) if assets_str else [])
                    
                    for asset in assets:
                        score = asset.get("score", {}).get("total_score", 0)
                        rendered_ad = asset.get("rendered_ad") or {}
                        preview = asset.get("preview") or {}
                        generated = asset.get("generated_creative") or {}
                        
                        all_creatives.append(
                            TopCreativeItem(
                                campaign_name=c_name,
                                campaign_slug=c_slug,
                                platform=c_plat,
                                concept_id=asset.get("concept_id"),
                                total_score=score,
                                primary_text=asset.get("primary_text"),
                                headline=asset.get("headline"),
                                description=asset.get("description"),
                                cta=asset.get("cta"),
                                image_urls=generated.get("image_urls", []),
                                video_urls=generated.get("video_urls", []),
                                rendered_image_path=rendered_ad.get("image_path"),
                                preview_image_path=preview.get("image_path"),
                                rendered_image_base64=rendered_ad.get("image_base64"),
                                preview_image_base64=preview.get("image_base64"),
                                output_directory="",
                            )
                        )
                
                # Sort by score descending
                all_creatives.sort(key=lambda x: x.total_score, reverse=True)
                
                if limit is not None:
                    all_creatives = all_creatives[:limit]
                    
                return TopCreativesResponse(items=all_creatives)
            except Exception as exc:
                logger.exception("Database fetch error: %s", exc)
                return TopCreativesResponse(items=[])
