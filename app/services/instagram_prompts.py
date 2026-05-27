import json

from app.models import InstagramReelsRequest, InstagramReelsResponse, ReelScript


INSTAGRAM_SYSTEM_PROMPT = (
    "You are the Instagram Script Writer & Director Agent inside Creative Director Engine. "
    "Think like a viral short-form strategist, creative director, performance marketer, and storyboard writer. "
    "Return only valid JSON. Keep every field specific, practical, and optimized for retention, shares, saves, and replayability."
)


def _serialize_request(request: InstagramReelsRequest) -> str:
    return json.dumps(request.model_dump(mode="json"), indent=2, ensure_ascii=True)


def analysis_prompt(request: InstagramReelsRequest) -> str:
    return (
        "Analyze the provided Instagram reel brief and any reference material. "
        "Return the strongest retention and virality patterns in a structured way.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        "Focus on: visual_hook, opening_line, emotional_trigger, pacing_style, scene_density, CTA_style, "
        "caption_pattern, audio_trend, competitor_pattern, and transition_pattern."
    )


def competitor_prompt(request: InstagramReelsRequest) -> str:
    return (
        "Analyze the competitor reels and identify repeatable winning formulas, content gaps, and reusable patterns. "
        "Explain why the formats win and what to borrow without copying.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        "Return a tactical competitor intelligence output."
    )


def trend_prompt(request: InstagramReelsRequest) -> str:
    return (
        "Detect reusable Instagram reel trends from the provided sample set. "
        "Return trend objects with saturation and viral probability.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        "Prefer trends that are adaptable across niches and that support retention-driven editing."
    )


def script_prompt(request: InstagramReelsRequest, analysis: InstagramReelsResponse) -> str:
    return (
        "Write a creator-ready Instagram reel script and director package. "
        "The output must be optimized for watch time, shares, saves, comments, and replayability.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        f"ANALYSIS_CONTEXT:\n{analysis.model_dump_json(indent=2)}\n\n"
        "Return a complete shoot-ready script with scene-by-scene direction, camera direction, B-roll, overlays, editing notes, "
        "sound design, CTA, caption, hashtags, thumbnail text, emotional progression, and retention strategy explanation."
    )


def director_prompt(request: InstagramReelsRequest, analysis: InstagramReelsResponse, script: ReelScript) -> str:
    return (
        "Direct this Instagram reel like a short-form film director. "
        "Create a second-by-second timeline, retention-critical moments, dopamine spikes, and interruption beats.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        f"ANALYSIS_CONTEXT:\n{analysis.model_dump_json(indent=2)}\n\n"
        f"SCRIPT:\n{script.model_dump_json(indent=2)}\n\n"
        "Return only structured JSON for production execution."
    )


def scoring_prompt(request: InstagramReelsRequest, analysis: InstagramReelsResponse, script: ReelScript) -> str:
    return (
        "Score this Instagram reel concept for hook strength, virality, retention, shareability, emotional impact, curiosity gap, "
        "thumbnail quality, and CTA effectiveness.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        f"ANALYSIS_CONTEXT:\n{analysis.model_dump_json(indent=2)}\n\n"
        f"SCRIPT:\n{script.model_dump_json(indent=2)}\n\n"
        "Return a scored breakdown and rationale."
    )