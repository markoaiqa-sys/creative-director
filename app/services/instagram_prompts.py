import json

from app.models import InstagramReelsRequest, InstagramReelsResponse, ReelScript

INSTAGRAM_SYSTEM_PROMPT = """
You are the core Instagram Reel Intelligence system inside Creative Director Engine.

You are not a chatbot and not a generic marketing assistant.
You operate as:
- viral strategist
- creative director
- retention analyst
- reel editor strategist
- competitor intelligence engine
- Instagram growth analyst
- cinematic storyboard director

Your primary job is to explain WHY reels work, HOW attention is held, WHAT competitors are repeating,
WHICH trend structures are rising, and HOW to generate a stronger reel that improves retention,
replayability, emotional intensity, curiosity loops, shares, saves, and comments.

Always reason in layers:
1. Hook analysis
   - opening line
   - first 3 seconds
   - curiosity gap
   - emotional trigger
   - tension creation
   - authority positioning
   - controversy potential
   - replay trigger
   - classify hook style when possible:
     Curiosity, Fear, Shock, Transformation, POV, Contrarian, Storytelling,
     Emotional confession, Tutorial hook, Proof hook, Relatable pain, Aspiration, Social proof

2. Visual hook analysis
   - face close-ups
   - zooms
   - subtitles
   - movement intensity
   - scene cuts
   - pattern interruptions
   - color energy
   - camera motion
   - visual density
   - subtitle timing
   - reaction shots

3. Retention analysis
   - retention spikes
   - replay moments
   - drop-off moments
   - emotional peaks
   - payoff timing
   - CTA timing quality

4. Trend intelligence
   - trending hook styles
   - storytelling structures
   - editing formats
   - captions
   - subtitle styles
   - pacing styles
   - audio formats
   - oversaturated patterns
   - emerging opportunities

5. Competitor intelligence
   - winning formulas
   - recurring hooks
   - CTA structure
   - pacing strategy
   - editing style
   - emotional rhythm
   - storytelling formula
   - subtitle patterns
   - audience manipulation tactics

6. Caption intelligence
   - caption psychology
   - CTA placement
   - emotional phrasing
   - save/comment triggers
   - formatting style
   - readability
   - audience targeting

7. Viral scoring
   - hook strength
   - curiosity
   - emotional trigger
   - retention potential
   - replayability
   - shareability
   - save potential
   - comment bait
   - viral probability
   - visual intensity
   - editing quality
   - audience targeting

Critical rules:
- Never give generic marketing advice.
- Never give vague viral suggestions.
- Always explain why something works psychologically.
- Always focus on audience behavior and retention pacing.
- Always identify replay triggers and interruption patterns.
- Think cinematically, not just copy-first.
- Return only valid JSON matching the response schema.
- Make every populated field specific, visual, and actionable.
""".strip()


def _serialize_request(request: InstagramReelsRequest) -> str:
    return json.dumps(request.model_dump(mode="json"), indent=2, ensure_ascii=True)


def _serialize_analysis(analysis: InstagramReelsResponse) -> str:
    # Restrict keys to essential fields to minimize token consumption and avoid 429 rate limits
    keys_to_keep = {
        "summary", "brand_name", "niche", "audience", "viral_probability_score",
        "hook_strength_score", "audience_retention_prediction", "retention_score",
        "hook_alternatives", "top_performing_patterns", "content_gaps",
        "reusable_winning_formulas", "recommendations", "assumptions", "audio_trend", "caption_pattern"
    }
    data = analysis.model_dump(mode="json")
    clean_data = {k: v for k, v in data.items() if k in keys_to_keep and v not in (None, "", [], {})}
    return json.dumps(clean_data, indent=2, ensure_ascii=True)


def analysis_prompt(request: InstagramReelsRequest) -> str:
    return (
        "Analyze the provided Instagram reel brief and reference material like an elite Reel Intelligence engine. "
        "Do not summarize loosely. Explain why the reel works across hook psychology, visual retention, pacing, emotion, replay triggers, "
        "competitor logic, caption behavior, and trend fit.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        "Populate the response so the frontend can show:\n"
        "- Section A: viral breakdown\n"
        "- Section B: visual hook timeline\n"
        "- Section C: retention graph\n"
        "- Section D: competitor analysis\n"
        "- Section E: trend analysis\n"
        "- Section F: viral DNA\n\n"
        "Focus on these insight categories explicitly: visual_hook, opening_line, emotional_trigger, pacing_style, "
        "scene_density, CTA_style, caption_pattern, audio_trend, competitor_pattern, and transition_pattern."
    )


def competitor_prompt(request: InstagramReelsRequest) -> str:
    return (
        "Analyze competitor reels deeply and extract reusable winning formulas, emotional rhythm, pacing strategy, editing style, "
        "hook repetition, CTA structure, subtitle behavior, and audience manipulation tactics. "
        "Explain why competitors are winning and how to outperform them without copying surface language.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        "Return a tactical competitor intelligence output with psychologically specific explanations."
    )


def trend_prompt(request: InstagramReelsRequest) -> str:
    return (
        "Detect reusable Instagram reel trends from the provided sample set. "
        "Identify rising trends, declining trends, oversaturated patterns, and emerging opportunities across hooks, captions, "
        "editing, pacing, subtitle behavior, and audio energy. Return trend objects with momentum and saturation awareness.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        "Prefer trends that are adaptable across niches and that support retention-driven editing and replayability."
    )


def script_prompt(request: InstagramReelsRequest, analysis: InstagramReelsResponse) -> str:
    return (
        "Write a creator-ready Instagram reel script and director package. "
        "This is not plain copywriting. Build a cinematic retention-first reel with emotional transitions, subtitle logic, edit rhythm, "
        "curiosity loops, payoff timing, replay triggers, and a strong CTA.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        f"ANALYSIS_CONTEXT:\n{_serialize_analysis(analysis)}\n\n"
        "Return a complete shoot-ready script with:\n"
        "- title\n"
        "- hook\n"
        "- spoken dialogue\n"
        "- subtitle overlays\n"
        "- pacing logic\n"
        "- emotional transitions\n"
        "- CTA\n"
        "- caption\n"
        "- hashtags\n"
        "- thumbnail text\n"
        "- retention strategy explanation\n"
        "- scene-by-scene direction"
    )


def director_prompt(request: InstagramReelsRequest, analysis: InstagramReelsResponse, script: ReelScript) -> str:
    return (
        "Direct this Instagram reel like a short-form film director. "
        "Build scene-by-scene cinematic direction with timestamp, dialogue, camera movement, subtitle style, B-roll, emotional goal, "
        "retention purpose, editing notes, transition style, and sound/music cue. "
        "Explicitly surface retention-critical moments, dopamine spikes, interruption beats, and visual pacing psychology.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        f"ANALYSIS_CONTEXT:\n{_serialize_analysis(analysis)}\n\n"
        f"SCRIPT:\n{script.model_dump_json(indent=2)}\n\n"
        "Return only structured JSON for production execution."
    )


def scoring_prompt(request: InstagramReelsRequest, analysis: InstagramReelsResponse, script: ReelScript) -> str:
    return (
        "Score this Instagram reel concept for hook strength, curiosity, emotional trigger, retention potential, replayability, "
        "shareability, save potential, comment bait, viral probability, visual intensity, editing quality, and audience targeting.\n\n"
        f"REQUEST:\n{_serialize_request(request)}\n\n"
        f"ANALYSIS_CONTEXT:\n{_serialize_analysis(analysis)}\n\n"
        f"SCRIPT:\n{script.model_dump_json(indent=2)}\n\n"
        "Return a scored breakdown and rationale. Scores must feel evidence-based, not random, and should explain why each category is high or low."
    )
