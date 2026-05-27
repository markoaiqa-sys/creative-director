from app.models import InstagramGenerateScriptRequest, InstagramReelsRequest, InstagramReelsResponse, ReelSceneBeat, ReelScript
from app.providers.groq_llm import GroqLLMProvider
from app.services.instagram_analyzer import InstagramAnalyzer
from app.services.instagram_prompts import INSTAGRAM_SYSTEM_PROMPT, script_prompt
from app.services.retention_scorer import RetentionScorer
from app.services.trend_detector import TrendDetector


class ScriptWriter:
    def __init__(
        self,
        llm: GroqLLMProvider | None,
        analyzer: InstagramAnalyzer,
        scorer: RetentionScorer,
        trend_detector: TrendDetector,
    ) -> None:
        self._llm = llm
        self._analyzer = analyzer
        self._scorer = scorer
        self._trend_detector = trend_detector

    async def generate(self, request: InstagramGenerateScriptRequest) -> InstagramReelsResponse:
        analysis = await self._analyzer.analyze_reel(request)
        heuristic_script = self._heuristic_script(request, analysis)
        structured = InstagramReelsResponse()

        if self._llm:
            try:
                structured = await self._llm.structured_completion(
                    instructions=INSTAGRAM_SYSTEM_PROMPT,
                    user_prompt=script_prompt(request, analysis),
                    response_model=InstagramReelsResponse,
                )
            except Exception:
                pass

        merged_script = self._merge_script(heuristic_script, structured.script)
        response = self._merge(analysis, structured, merged_script)
        trends = self._trend_detector.detect(
            brief=request.brief,
            trending_reels=request.trending_reels,
            competitor_reels=request.competitor_reels,
            normalized_reels=request.normalized_reels,
            niche=request.niche,
            audience=request.audience,
        )
        scores = self._scorer.score(
            request=request,
            analysis=response.analysis,
            trends=trends,
            script=merged_script,
            normalized_reels=request.normalized_reels,
        )
        response.scores = scores
        response.viral_probability_score = max(response.viral_probability_score, scores.virality, scores.total_score)
        response.hook_strength_score = max(response.hook_strength_score, scores.hook_strength)
        response.audience_retention_prediction = max(response.audience_retention_prediction, scores.retention)
        response.retention_score = max(response.retention_score, scores.retention)
        if not response.trend_objects:
            response.trend_objects = trends
        return response

    def _heuristic_script(self, request: InstagramReelsRequest, analysis: InstagramReelsResponse) -> ReelScript:
        hook = analysis.hook_alternatives[0] if analysis.hook_alternatives else request.brief
        beat_seconds = ["0-2", "3-5", "6-10", "11-15", "16-22", "23-30"]
        scenes: list[ReelSceneBeat] = []
        for index, second_range in enumerate(beat_seconds):
            scenes.append(
                ReelSceneBeat(
                    second_range=second_range,
                    scene=[
                        "Instant hook",
                        "Establish the problem",
                        "Show a fast proof point",
                        "Reveal the mechanism",
                        "Raise the stakes",
                        "Deliver CTA and close",
                    ][index],
                    camera_direction=[
                        "tight close-up with hard crop",
                        "slow push-in",
                        "quick cut to proof",
                        "over-the-shoulder detail",
                        "slight zoom and pause",
                        "direct-to-camera finish",
                    ][index],
                    b_roll=[
                        "Text-first hook frame",
                        "Problem visual",
                        "Proof or result visual",
                        "Process step visual",
                        "Emphasis cutaway",
                        "CTA end card",
                    ][index:index + 1],
                    text_overlay=[hook if index == 0 else request.brief],
                    editing_notes=["Cut on motion", "Keep the first beat under 2 seconds"],
                    sound_design=["clean beat", "subtle riser"],
                    facial_expression="confident and direct",
                    emotional_intent=["curiosity", "friction", "relief", "confidence", "urgency", "commitment"][index],
                    retention_note=[
                        "Interrupt scrolling immediately.",
                        "Keep the gap open.",
                        "Reward attention quickly.",
                        "Explain the mechanism without overtalking.",
                        "Spike intensity before the CTA.",
                        "Close with a clear next step.",
                    ][index],
                    transition_timing=["0.3s", "0.5s", "0.4s", "0.5s", "0.3s", "0.4s"][index],
                    interruption_pattern=index in {0, 2, 4},
                )
            )

        return ReelScript(
            title=f"{request.brand_name or 'Instagram'} Reel Script",
            viral_probability_score=analysis.viral_probability_score,
            hook_strength_score=analysis.hook_strength_score,
            audience_retention_prediction=analysis.audience_retention_prediction,
            spoken_script="\n".join([
                f"Hook: {hook}",
                f"Problem: {request.brief}",
                "Proof: show the transformation or mechanism.",
                f"CTA: {request.call_to_action or 'Comment for the template.'}",
            ]),
            scene_by_scene_direction=scenes,
            camera_direction="High-contrast, fast-start, text-led camera language with one clean reset every few seconds.",
            b_roll_suggestions=["close-up proof", "process detail", "reaction cutaway", "before/after frame", "end card"],
            caption_overlays=[hook, request.brief, request.call_to_action or "Comment for the full breakdown"],
            editing_notes=["Front-load the promise", "Avoid long intros", "Use visible resets every 2-4 seconds"],
            sound_design_suggestions=[request.audio_trend_hint or "minimal pulse", "subtle impact hits", "small risers at transitions"],
            cta=request.call_to_action or "Comment for the breakdown",
            instagram_caption=analysis.instagram_caption,
            hashtag_suggestions=analysis.hashtags,
            thumbnail_text=analysis.thumbnail_text or hook,
            emotional_progression=["curiosity", "friction", "proof", "relief", "action"],
            retention_strategy_explanation="The reel opens with a pattern break, moves to proof quickly, then alternates tension and payoff so the viewer keeps expecting resolution.",
            second_by_second_timeline=scenes,
            retention_critical_moments=["first 2 seconds", "first proof beat", "before CTA"],
            dopamine_spikes=["opening contradiction", "proof reveal", "rapid payoff"],
            interruption_pattern_moments=["0-2s hook", "6-10s proof reset", "16-22s payoff spike"],
        )

    @staticmethod
    def _merge(analysis: InstagramReelsResponse, structured: InstagramReelsResponse, script: ReelScript) -> InstagramReelsResponse:
        data = analysis.model_dump(mode="json")
        overlay = structured.model_dump(exclude_unset=True, mode="json")
        for key, value in overlay.items():
            if value not in (None, "", [], {}):
                data[key] = value
        data["script"] = script.model_dump(mode="json")
        data["full_script"] = script.scene_by_scene_direction
        data["second_by_second_timeline"] = script.second_by_second_timeline
        data["thumbnail_text"] = script.thumbnail_text
        data["instagram_caption"] = script.instagram_caption
        data["hashtags"] = script.hashtag_suggestions
        return InstagramReelsResponse.model_validate(data)

    @staticmethod
    def _merge_script(base: ReelScript, overlay: ReelScript) -> ReelScript:
        if not overlay:
            return base
        data = base.model_dump(mode="json")
        overlay_data = overlay.model_dump(exclude_unset=True, mode="json")
        for key, value in overlay_data.items():
            if value not in (None, "", [], {}):
                data[key] = value
        return ReelScript.model_validate(data)
