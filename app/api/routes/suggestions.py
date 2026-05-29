from fastapi import APIRouter
from pydantic import BaseModel
import httpx
import json
from app.core.config import get_settings

router = APIRouter()


class SuggestionRequest(BaseModel):
    campaign: dict


class Suggestion(BaseModel):
    id: str
    title: str
    description: str
    category: str
    action_type: str
    target: str | None = None


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]


class ExecuteRequest(BaseModel):
    suggestion: Suggestion
    campaign: dict


class ExecuteResponse(BaseModel):
    action_type: str
    updated_items: list[dict]
    message: str


SUGGESTION_SYSTEM = """You are a senior performance marketer analyzing an ad campaign output.

Given the campaign data, generate exactly 4 actionable suggestions across these 3 categories:
- content_quality: Based on pattern/variety of generated hooks and copy
- strategy_gap: Based on the brief, audience, competitors, and what is missing
- copy_optimization: Based on scores and headline/copy strength

Return a JSON object with this exact structure:
{
  "suggestions": [
    {
      "id": "s1",
      "title": "Short actionable title (max 8 words)",
      "description": "One sentence: what to do and why it will improve performance.",
      "category": "content_quality|strategy_gap|copy_optimization",
      "action_type": "rewrite_hook|add_hook|add_angle|rewrite_copy",
      "target": "specific item name or null"
    }
  ]
}

Rules:
- Mix categories: at least 1 from each category
- Be specific — reference actual content from the campaign
- Each suggestion must be immediately executable
- No generic advice like improve your copy"""


EXECUTE_SYSTEM = """You are a senior performance marketer executing a specific creative improvement.

Given the campaign data and the suggestion to execute, perform the action and return the result.

Return a JSON object with this exact structure:
{
  "updated_items": [
    {
      "type": "hook|angle|copy",
      "data": { ... full item matching original schema ... }
    }
  ],
  "message": "One sentence confirming what was done."
}

For hooks: include fields: type, text, rationale
For angles: include fields: name, description, target_emotion, use_case
For copy: include fields: headline, primary_text, cta, hook_text, angle_name, total_score, score_rank, score_rationale"""


@router.post("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(request: SuggestionRequest):
    settings = get_settings()

    campaign = request.campaign
    hooks = campaign.get("hooks", [])
    angles = campaign.get("angles", [])
    copies = campaign.get("copies", [])
    concepts = campaign.get("concepts", [])

    hooks_summary = json.dumps([{"type": h.get("type"), "text": h.get("text")} for h in hooks[:10]], indent=2)
    angles_summary = json.dumps([{"name": a.get("name"), "description": a.get("description"), "emotion": a.get("target_emotion")} for a in angles], indent=2)
    copies_summary = json.dumps([{"headline": c.get("headline"), "primary_text": c.get("primary_text"), "score": c.get("total_score"), "cta": c.get("cta")} for c in copies[:5]], indent=2)
    concepts_summary = json.dumps([{"id": c.get("concept_id"), "media_type": c.get("media_type"), "scene": c.get("scene_description")} for c in concepts], indent=2)

    campaign_summary = f"""
HOOKS ({len(hooks)}):
{hooks_summary}

ANGLES ({len(angles)}):
{angles_summary}

TOP COPY ({len(copies)}):
{copies_summary}

CONCEPTS ({len(concepts)}):
{concepts_summary}
"""

    try:
        from app.providers.groq_llm import custom_groq_key_var
        custom_key = custom_groq_key_var.get()
        api_key = custom_key if custom_key else settings.groq_api_key

        async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds) as client:
            response = await client.post(
                f"{settings.groq_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.groq_model,
                    "messages": [
                        {"role": "system", "content": SUGGESTION_SYSTEM},
                        {"role": "user", "content": campaign_summary},
                    ],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = json.loads(data["choices"][0]["message"]["content"])
            suggestions = [Suggestion(**s) for s in content.get("suggestions", [])]
            return SuggestionsResponse(suggestions=suggestions[:4])

    except Exception as e:
        return SuggestionsResponse(suggestions=[
            Suggestion(id="s1", title="Add a curiosity-based hook", description="Balance your hook variety by adding a curiosity hook to improve CTR on cold audiences.", category="content_quality", action_type="add_hook", target=None),
            Suggestion(id="s2", title="Add a comparison angle", description="A direct competitor comparison angle can sharpen positioning against your competitors.", category="strategy_gap", action_type="add_angle", target=None),
            Suggestion(id="s3", title="Rewrite top copy headline", description="Make the headline more specific with a number or outcome to increase relevance score.", category="copy_optimization", action_type="rewrite_copy", target="top"),
            Suggestion(id="s4", title="Add a social proof hook", description="None of your hooks use social proof — adding one can significantly boost trust on paid channels.", category="content_quality", action_type="add_hook", target=None),
        ])


@router.post("/execute-suggestion", response_model=ExecuteResponse)
async def execute_suggestion(request: ExecuteRequest):
    settings = get_settings()

    suggestion = request.suggestion
    campaign = request.campaign

    context = f"""
SUGGESTION TO EXECUTE:
Title: {suggestion.title}
Description: {suggestion.description}
Action: {suggestion.action_type}
Target: {suggestion.target or 'none'}

CURRENT CAMPAIGN DATA:
{json.dumps(campaign, indent=2)[:3000]}
"""

    try:
        from app.providers.groq_llm import custom_groq_key_var
        custom_key = custom_groq_key_var.get()
        api_key = custom_key if custom_key else settings.groq_api_key

        async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds) as client:
            response = await client.post(
                f"{settings.groq_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.groq_model,
                    "messages": [
                        {"role": "system", "content": EXECUTE_SYSTEM},
                        {"role": "user", "content": context},
                    ],
                    "temperature": 0.6,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = json.loads(data["choices"][0]["message"]["content"])
            return ExecuteResponse(
                action_type=suggestion.action_type,
                updated_items=content.get("updated_items", []),
                message=content.get("message", "Suggestion executed."),
            )

    except Exception as e:
        return ExecuteResponse(
            action_type=suggestion.action_type,
            updated_items=[],
            message=f"Execution failed: {str(e)}",
        )