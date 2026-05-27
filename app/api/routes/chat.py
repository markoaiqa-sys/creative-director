import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel
import httpx
from app.core.config import get_settings

router = APIRouter()
log = logging.getLogger("chat")


class ChatRequest(BaseModel):
    message: str
    context: dict | None = None
    session_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    context: dict | None = None
    session_id: str | None = None


from fastapi import APIRouter, Header, Request, Depends

SPECIALIST_SYSTEM_PROMPTS = {
    "reels": (
        "You are Marko's core Instagram Reel Intelligence specialist. "
        "Think like a viral strategist, creative director, retention analyst, competitor intelligence engine, "
        "Instagram growth analyst, and cinematic storyboard director. "
        "Focus on why reels go viral, opening hooks, visual hooks, emotional triggers, pattern interruptions, "
        "editing rhythm, replay triggers, competitor formulas, caption psychology, trend momentum, and scene-by-scene direction."
    )
}

class ReelsDirectorRequest(BaseModel):
    message: str
    context: dict | None = None
    session_id: str | None = None
    brand_name: str | None = None
    niche: str | None = None
    competitors: list[str] | None = None
    trending_reels: list[dict] | None = None
    competitor_reels: list[dict] | None = None


class ReelsDirectorResponse(BaseModel):
    reply: str
    analysis: dict | None = None
    context: dict | None = None
    session_id: str | None = None

@router.post("/chat-assistant", response_model=ChatResponse)
async def chat_assistant(
    request: ChatRequest,
    x_client_email: str | None = Header(None),
    x_is_guest: str | None = Header(None)
):
    settings = get_settings()
    from app.services.database import ChatDatabase
    import uuid
    chat_db = ChatDatabase(settings)
    session_id = request.session_id or str(uuid.uuid4())

    context = request.context or {}
    active_specialist = context.get("active_specialist")
    history = context.get("history", [])
    campaign = context.get("campaign", {})

    campaign_summary = ""
    if campaign:
        hooks = campaign.get("hooks", [])
        angles = campaign.get("angles", [])
        copies = campaign.get("copies", [])
        concepts = campaign.get("concepts", [])
        parts = []
        if hooks:
            parts.append("HOOKS:\n" + "\n".join(f"- [{h.get('type','')}] {h.get('text','')}" for h in hooks[:5]))
        if angles:
            parts.append("ANGLES:\n" + "\n".join(f"- {a.get('name','')}: {a.get('description','')}" for a in angles[:3]))
        if copies:
            parts.append("TOP COPY:\n" + "\n".join(f"- {c.get('headline','')}: {c.get('primary_text','')}" for c in copies[:3]))
        if concepts:
            parts.append("CONCEPTS:\n" + "\n".join(f"- {c.get('concept_id','')}: {c.get('scene_description','')}" for c in concepts[:2]))
        if parts:
            campaign_summary = "\n\nCURRENT CAMPAIGN OUTPUT:\n" + "\n\n".join(parts)

    specialist_guidance = SPECIALIST_SYSTEM_PROMPTS.get(active_specialist, "")
    specialist_text = f"\n\nSpecialist mode:\n{specialist_guidance}" if specialist_guidance else ""

    system = f"""You are Marko, a sharp AI assistant built into Marko AI — an agentic platform for generating ad hooks, angles, copy, and visual concepts.

Rules:
- Reply in 1-2 sentences max. No fluff, no filler.
- Be direct. Lead with the answer, not context.
- If asked about the generated content, reference it specifically.
- If asked something off-topic, briefly answer and steer back to marketing/ads.
- Never say "Great question", "Of course", "Certainly", or any preamble.
- Tone: confident, sharp, like a senior growth marketer.{campaign_summary}{specialist_text}"""

    messages = [{"role": "system", "content": system}]
    for entry in history[-10:]:
        messages.append(entry)
    messages.append({"role": "user", "content": request.message})

    error_msgs: list[str] = []
    reply: str | None = None
    hit_rate_limit = False

    # --- Try Groq first ---
    if settings.groq_api_key:
        try:
            async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.groq_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.groq_model,
                        "messages": messages,
                        "max_tokens": 512,
                        "temperature": 0.7,
                    },
                )
                if response.status_code == 429:
                    hit_rate_limit = True
                    log.warning("[CHAT] Groq returned 429 Too Many Requests — will try Gemini")
                    error_msgs.append("Groq: rate limited (429)")
                else:
                    response.raise_for_status()
                    data = response.json()
                    reply = data["choices"][0]["message"]["content"].strip()
                    log.info("[CHAT] Groq responded OK")
        except Exception as exc:
            log.warning(f"[CHAT] Groq failed: {exc}")
            error_msgs.append(f"Groq error: {exc}")
    else:
        log.warning("[CHAT] groq_api_key not configured — skipping Groq")

    # --- Fall back to Gemini with retry on 429 ---
    if not reply and settings.gemini_api_key:
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                gemini_messages = []
                system_instruction = ""
                for msg in messages:
                    if msg["role"] == "system":
                        system_instruction = msg["content"]
                    elif msg["role"] == "user":
                        gemini_messages.append({"role": "user", "parts": [{"text": msg["content"]}]})
                    elif msg["role"] == "assistant":
                        gemini_messages.append({"role": "model", "parts": [{"text": msg["content"]}]})

                async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds) as client:
                    url = f"{settings.gemini_base_url}/{settings.gemini_model}:generateContent"
                    payload: dict = {
                        "contents": gemini_messages,
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 512,
                        }
                    }
                    if system_instruction:
                        payload["system_instruction"] = {
                            "parts": [{"text": system_instruction}]
                        }

                    response = await client.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        params={"key": settings.gemini_api_key},
                        json=payload
                    )

                    if response.status_code == 429:
                        hit_rate_limit = True
                        wait_secs = 4 * (attempt + 1)
                        log.warning(
                            f"[CHAT] Gemini 429 (attempt {attempt + 1}/{max_attempts}) — "
                            f"{'retrying in ' + str(wait_secs) + 's' if attempt < max_attempts - 1 else 'giving up'}"
                        )
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(wait_secs)
                            continue
                        else:
                            error_msgs.append("Gemini: rate limited (429)")
                            break

                    response.raise_for_status()
                    data = response.json()
                    reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    log.info("[CHAT] Gemini responded OK")
                    break

            except Exception as exc:
                log.warning(f"[CHAT] Gemini error (attempt {attempt + 1}): {exc}")
                error_msgs.append(f"Gemini error: {exc}")
                break
    elif not reply:
        log.warning("[CHAT] gemini_api_key not configured — no fallback available")

    # --- Return reply or friendly error ---
    if reply:
        is_guest_bool = x_is_guest == "true"
        chat_db.save_message(session_id, "user", request.message, client_email=x_client_email, is_guest=is_guest_bool)
        chat_db.save_message(session_id, "assistant", reply, client_email=x_client_email, is_guest=is_guest_bool)
        new_history = history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": reply},
        ]
        return ChatResponse(reply=reply, context={"history": new_history}, session_id=session_id)
    else:
        if hit_rate_limit:
            friendly = (
                "The AI assistant is rate-limited right now. "
                "Please wait 10–15 seconds and try again."
            )
        else:
            errors = " | ".join(error_msgs) or "No API keys configured."
            friendly = f"Sorry, I couldn't reach the AI backend. ({errors})"
        log.error(f"[CHAT] All providers failed: {' | '.join(error_msgs)}")
        return ChatResponse(reply=friendly, context=request.context, session_id=session_id)


@router.post("/reels-director", response_model=ReelsDirectorResponse)
async def reels_director(
    request: ReelsDirectorRequest,
    http_request: Request,
    x_client_email: str | None = Header(None),
    x_is_guest: str | None = Header(None),
):
    settings = get_settings()
    from app.services.database import ChatDatabase
    import uuid

    chat_db = ChatDatabase(settings)
    session_id = request.session_id or str(uuid.uuid4())
    context = request.context or {}
    history = context.get("history", [])
    container = http_request.app.state.container
    instagram_engine = container.instagram_engine

    from app.models import InstagramDirectReelRequest, NormalizedReelData

    ingestion = context.get("instagram_ingestion") or {}
    ingestion_result = ingestion.get("result") or {}
    normalized_reels_raw = ingestion_result.get("reels") or []
    normalized_reels: list[NormalizedReelData] = []
    for item in normalized_reels_raw[:100]:
        try:
            normalized_reels.append(NormalizedReelData.model_validate(item))
        except Exception:
            continue

    reels_payload = InstagramDirectReelRequest.model_validate(
        {
            "brief": request.message,
            "brand_name": request.brand_name or context.get("brand_name"),
            "niche": request.niche or context.get("niche"),
            "audience": context.get("audience"),
            "extra_context": str(context.get("campaign", {}))[:3000],
            "competitor_reels": request.competitor_reels or [],
            "trending_reels": request.trending_reels or [],
            "instagram_usernames": request.competitors or [],
            "call_to_action": context.get("cta"),
            "normalized_reels": [item.model_dump(mode="json") for item in normalized_reels],
            "duration_seconds": 30,
        }
    )

    try:
        result = await instagram_engine.direct_reel(reels_payload)
    except Exception as exc:
        fallback_reply = f"I could not complete structured reels analysis right now. ({exc})"
        return ReelsDirectorResponse(reply=fallback_reply, analysis=None, context=context, session_id=session_id)

    reply = "Instagram Reels analysis is ready: viral patterns, competitor wins, script direction, and retention scoring."
    is_guest_bool = x_is_guest == "true"
    chat_db.save_message(session_id, "user", request.message, client_email=x_client_email, is_guest=is_guest_bool)
    chat_db.save_message(session_id, "assistant", reply, client_email=x_client_email, is_guest=is_guest_bool)
    new_history = history + [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": reply},
    ]
    new_context = {**context, "history": new_history, "last_reels_analysis": result.model_dump(mode="json"), "active_specialist": "reels"}
    return ReelsDirectorResponse(reply=reply, analysis=result.model_dump(mode="json"), context=new_context, session_id=session_id)

@router.get("/chat-history/{session_id}")
async def get_chat_history(
    session_id: str,
    x_client_email: str | None = Header(None)
):
    settings = get_settings()
    from app.services.database import ChatDatabase
    chat_db = ChatDatabase(settings)
    history = chat_db.get_history(session_id, client_email=x_client_email)
    return {"session_id": session_id, "history": history}

@router.get("/chat-sessions")
async def get_chat_sessions(
    x_client_email: str | None = Header(None)
):
    settings = get_settings()
    from app.services.database import ChatDatabase
    chat_db = ChatDatabase(settings)
    sessions = chat_db.get_sessions(client_email=x_client_email)
    return {"sessions": sessions}

@router.get("/session-data/{session_id}")
async def get_session_data(
    session_id: str,
    x_client_email: str | None = Header(None)
):
    """Get all session data: chat history, knowledge base, and execution history."""
    settings = get_settings()
    from app.services.database import ChatDatabase
    chat_db = ChatDatabase(settings)
    
    chat_history = chat_db.get_history(session_id, client_email=x_client_email)
    knowledge_base = chat_db.get_knowledge_base(session_id)
    execution_history = chat_db.get_execution_history(session_id)
    
    return {
        "session_id": session_id,
        "chat_history": chat_history,
        "knowledge_base": knowledge_base,
        "execution_history": execution_history,
    }

@router.post("/knowledge-base/{session_id}")
async def save_knowledge_base(
    session_id: str,
    kb_item: dict,
    x_is_guest: str | None = Header(None)
):
    """Save a knowledge base item to the session."""
    settings = get_settings()
    from app.services.database import ChatDatabase
    chat_db = ChatDatabase(settings)
    
    is_guest_bool = x_is_guest == "true"
    kb_id = chat_db.save_knowledge_base_item(
        session_id=session_id,
        file_name=kb_item.get("file_name", "unknown"),
        file_type=kb_item.get("file_type", "text"),
        file_path=kb_item.get("file_path", ""),
        file_content=kb_item.get("file_content"),
        metadata=kb_item.get("metadata", {}),
        is_guest=is_guest_bool
    )
    
    return {"success": kb_id is not None, "kb_id": kb_id, "session_id": session_id}

@router.get("/knowledge-base/{session_id}")
async def get_knowledge_base(session_id: str):
    """Retrieve all knowledge base items for a session."""
    settings = get_settings()
    from app.services.database import ChatDatabase
    chat_db = ChatDatabase(settings)
    
    knowledge_base = chat_db.get_knowledge_base(session_id)
    return {"session_id": session_id, "knowledge_base": knowledge_base}

@router.post("/execution-history/{session_id}")
async def save_execution_history(
    session_id: str,
    execution: dict,
    x_is_guest: str | None = Header(None)
):
    """Save execution/generation history."""
    settings = get_settings()
    from app.services.database import ChatDatabase
    import time
    
    chat_db = ChatDatabase(settings)
    start_time = time.time()
    
    is_guest_bool = x_is_guest == "true"
    execution_id = chat_db.save_execution_history(
        session_id=session_id,
        campaign_name=execution.get("campaign_name", "unknown"),
        execution_type=execution.get("execution_type", "generation"),
        input_data=execution.get("input_data", {}),
        output_data=execution.get("output_data", {}),
        status=execution.get("status", "success"),
        error_message=execution.get("error_message"),
        execution_time_ms=int((time.time() - start_time) * 1000),
        is_guest=is_guest_bool
    )
    
    return {"success": execution_id is not None, "execution_id": execution_id, "session_id": session_id}

@router.get("/execution-history/{session_id}")
async def get_execution_history(session_id: str):
    """Retrieve execution history for a session."""
    settings = get_settings()
    from app.services.database import ChatDatabase
    chat_db = ChatDatabase(settings)
    
    execution_history = chat_db.get_execution_history(session_id)
    return {"session_id": session_id, "execution_history": execution_history}


# ---------------------------------------------------------------------------
# Chatbot-driven campaign generation
# ---------------------------------------------------------------------------

CAMPAIGN_EXTRACT_SYSTEM = """You are Marko, an AI marketing assistant. Your job is to help users generate ad campaigns by extracting campaign parameters from their natural language messages.

REQUIRED FIELDS (campaign cannot be generated without these):
- brand_name: The brand or company name
- product_description: What the product/service does (at least 10 chars)
- target_audience: Who the ads target (at least 3 chars)
- platform: One of "meta", "google", "tiktok" (default: "meta")
- objective: One of "conversions", "traffic", "awareness" (default: "conversions")
- tone: MUST be one of: "premium", "casual", "bold", "friendly", "urgent" (pick the closest match)
- key_benefits: List of product benefits (at least 1 item)

OPTIONAL FIELDS:
- competitors: List of competitor brand names
- visual_style: Description of desired visual style
- brand_colors: List of hex colors
- brand_fonts: List of font names
- campaign_name: Custom campaign name
- extra_details: Any other important instructions, constraints, or offers mentioned by the user (e.g., "Use 20% off discount", "Must include a call to action for Friday")

INSTRUCTIONS:
1. Analyze the ENTIRE conversation history to extract as many fields as possible.
2. If ALL required fields can be determined from the conversation, respond with action "generate".
3. If any required fields are still missing, respond with action "ask_details".
4. Be smart about inferring fields — e.g. if user says "Zomato", you can infer product_description as "Online food delivery platform" and key_benefits as ["Fast delivery", "Wide restaurant selection", "Easy ordering"].
5. For well-known brands, use your knowledge to fill in reasonable defaults.

RESPOND WITH ONLY A JSON OBJECT in this exact format:
{
  "action": "generate" or "ask_details",
  "reply": "Your conversational reply to the user",
  "extracted": {
    "brand_name": "...",
    "product_description": "...",
    "target_audience": "...",
    "platform": "meta",
    "objective": "conversions",
    "tone": "...",
    "key_benefits": ["..."],
    "competitors": [],
    "visual_style": "",
    "brand_colors": [],
    "brand_fonts": [],
    "campaign_name": "",
    "extra_details": ""
  },
  "missing_fields": ["field1", "field2"]
}

If action is "ask_details", list specific missing fields in "missing_fields" and ask for them naturally in "reply".
If action is "generate", "missing_fields" should be empty and "extracted" must have all required fields filled.
Always include the "extracted" object with whatever you've gathered so far."""


class ChatGenerateRequest(BaseModel):
    message: str
    context: dict | None = None
    session_id: str | None = None


class ChatGenerateResponse(BaseModel):
    action: str  # "generate", "ask_details", or "chat"
    reply: str
    extracted: dict | None = None
    missing_fields: list[str] = []
    context: dict | None = None
    session_id: str | None = None


@router.post("/chat-generate", response_model=ChatGenerateResponse)
async def chat_generate(
    request: ChatGenerateRequest,
    x_client_email: str | None = Header(None),
    x_is_guest: str | None = Header(None)
):
    """Chatbot endpoint that extracts campaign parameters and triggers generation."""
    settings = get_settings()
    from app.services.database import ChatDatabase
    import uuid
    import json as json_module

    chat_db = ChatDatabase(settings)
    session_id = request.session_id or str(uuid.uuid4())

    context = request.context or {}
    history = context.get("history", [])
    accumulated = context.get("accumulated_params", {})

    # Build messages for the LLM
    messages = [{"role": "system", "content": CAMPAIGN_EXTRACT_SYSTEM}]

    # Include conversation history
    for entry in history[-10:]:
        messages.append(entry)

    # Add context about previously accumulated parameters
    user_content = request.message
    if accumulated:
        user_content += f"\n\n[PREVIOUSLY EXTRACTED PARAMETERS: {json_module.dumps(accumulated)}]"

    messages.append({"role": "user", "content": user_content})

    reply_text = ""
    parsed = None

    # --- Try Groq first ---
    if settings.groq_api_key:
        try:
            async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.groq_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.groq_model,
                        "messages": messages,
                        "max_tokens": 1024,
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"},
                    },
                )
                if response.status_code != 429:
                    response.raise_for_status()
                    data = response.json()
                    reply_text = data["choices"][0]["message"]["content"].strip()
                    log.info("[CHAT-GEN] Groq responded OK")
                else:
                    log.warning("[CHAT-GEN] Groq 429, trying Gemini")
        except Exception as exc:
            log.warning(f"[CHAT-GEN] Groq failed: {exc}")

    # --- Fall back to Gemini ---
    if not reply_text and settings.gemini_api_key:
        try:
            gemini_messages = []
            system_instruction = ""
            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    gemini_messages.append({"role": "user", "parts": [{"text": msg["content"]}]})
                elif msg["role"] == "assistant":
                    gemini_messages.append({"role": "model", "parts": [{"text": msg["content"]}]})

            async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds) as client:
                url = f"{settings.gemini_base_url}/{settings.gemini_model}:generateContent"
                payload = {
                    "contents": gemini_messages,
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 1024,
                        "responseMimeType": "application/json",
                    },
                }
                if system_instruction:
                    payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    params={"key": settings.gemini_api_key},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                reply_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                log.info("[CHAT-GEN] Gemini responded OK")
        except Exception as exc:
            log.warning(f"[CHAT-GEN] Gemini failed: {exc}")

    # --- Parse JSON response ---
    if reply_text:
        try:
            parsed = json_module.loads(reply_text)
        except json_module.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', reply_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json_module.loads(json_match.group(1))
                except Exception:
                    pass

    if not parsed:
        # LLM failed — attempt regex-based extraction as a last resort
        import re
        log.warning("[CHAT-GEN] LLM extraction failed, attempting regex fallback")
        msg = request.message

        brand_match = re.search(r'(?:for|brand[:\s]*)\s+([A-Z][a-zA-Z0-9 ]+?)(?:\.|,|\s+It)', msg)
        brand_name = brand_match.group(1).strip() if brand_match else ""

        # Product description: "It's a ..." until the next sentence boundary with "targeting"
        desc_match = re.search(r"[Ii]t'?s\s+(?:a|an)\s+(.+?)(?:\s+targeting|\.\s)", msg, re.DOTALL)
        product_desc = desc_match.group(1).strip() if desc_match else ""

        audience_match = re.search(r'targeting\s+(.+?)(?:\.|,\s*Use|\s+Use)', msg, re.IGNORECASE)
        target_audience = audience_match.group(1).strip() if audience_match else ""

        tone_match = re.search(r'(?:Use\s+(?:a\s+)?)([\w,\s]+?)\s+tone', msg, re.IGNORECASE)
        tone = tone_match.group(1).strip().split(",")[0].strip().lower() if tone_match else "premium"
        valid_tones = {"premium", "casual", "bold", "friendly", "urgent"}
        if tone not in valid_tones:
            tone = "premium"

        platform_match = re.search(r'for\s+(Meta|Google|TikTok)\s', msg, re.IGNORECASE)
        platform = platform_match.group(1).strip().lower() if platform_match else "meta"

        objective_match = re.search(r'(?:Meta|Google|TikTok)\s+(conversions|traffic|awareness)', msg, re.IGNORECASE)
        objective = objective_match.group(1).strip().lower() if objective_match else "conversions"

        benefits_match = re.search(r'[Kk]ey benefits?[:\s]+(.+?)(?:\.\s*[A-Z]|\.\s*$|$)', msg, re.DOTALL)
        benefits = []
        if benefits_match:
            raw_benefits = benefits_match.group(1).strip().rstrip(".")
            benefits = [b.strip() for b in raw_benefits.split(",") if b.strip()]

        competitors_match = re.search(r'[Cc]ompetitors?[:\s]+(.+?)(?:\.\s*|$)', msg)
        competitors = []
        if competitors_match:
            raw_comp = competitors_match.group(1).strip().rstrip(".")
            competitors = [c.strip() for c in raw_comp.split(",") if c.strip()]

        if brand_name and product_desc and target_audience and benefits:
            parsed = {
                "action": "generate",
                "reply": f"Great! I've got everything I need for {brand_name}. Let me generate your campaign now!",
                "extracted": {
                    "brand_name": brand_name,
                    "product_description": product_desc,
                    "target_audience": target_audience,
                    "platform": platform,
                    "objective": objective,
                    "tone": tone,
                    "key_benefits": benefits,
                    "competitors": competitors,
                    "visual_style": "",
                    "brand_colors": [],
                    "brand_fonts": [],
                    "campaign_name": "",
                },
                "missing_fields": [],
            }
            log.info(f"[CHAT-GEN] Regex fallback extracted: brand={brand_name}, audience={target_audience}")
        else:
            log.warning(f"[CHAT-GEN] Regex fallback incomplete: brand={brand_name!r}, desc={product_desc!r}, audience={target_audience!r}, benefits={benefits!r}")

    if not parsed:
        fallback_reply = "I'd love to help you generate a campaign! Tell me about the brand, product, target audience, and preferred tone."
        is_guest_bool = x_is_guest == "true"
        chat_db.save_message(session_id, "user", request.message, client_email=x_client_email, is_guest=is_guest_bool)
        chat_db.save_message(session_id, "assistant", fallback_reply, client_email=x_client_email, is_guest=is_guest_bool)
        
        # Both LLM and regex fallback failed — return a friendly message
        return ChatGenerateResponse(
            action="chat",
            reply=fallback_reply,
            context={"history": history + [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": fallback_reply},
            ]},
            session_id=session_id,
        )

    action = parsed.get("action", "chat")
    reply = parsed.get("reply", "")
    extracted = parsed.get("extracted", {})
    missing = parsed.get("missing_fields", [])

    # Merge newly extracted params with previously accumulated ones
    merged = {**accumulated}
    for key, value in extracted.items():
        if value and value != "" and value != []:
            merged[key] = value

    # Save chat messages
    is_guest_bool = x_is_guest == "true"
    chat_db.save_message(session_id, "user", request.message, client_email=x_client_email, is_guest=is_guest_bool)
    chat_db.save_message(session_id, "assistant", reply, client_email=x_client_email, is_guest=is_guest_bool)

    new_history = history + [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": reply},
    ]

    return ChatGenerateResponse(
        action=action,
        reply=reply,
        extracted=merged,
        missing_fields=missing,
        context={
            "history": new_history,
            "accumulated_params": merged,
        },
        session_id=session_id,
    )
