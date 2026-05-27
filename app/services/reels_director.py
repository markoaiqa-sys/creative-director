from app.models import InstagramDirectReelRequest, InstagramReelsResponse, ReelSceneBeat
from app.providers.groq_llm import GroqLLMProvider
from app.services.instagram_analyzer import InstagramAnalyzer
from app.services.instagram_prompts import INSTAGRAM_SYSTEM_PROMPT, director_prompt
from app.services.script_writer import ScriptWriter


class ReelsDirector:
    def __init__(self, llm: GroqLLMProvider | None, script_writer: ScriptWriter, analyzer: InstagramAnalyzer) -> None:
        self._llm = llm
        self._script_writer = script_writer
        self._analyzer = analyzer

    async def direct(self, request: InstagramDirectReelRequest) -> InstagramReelsResponse:
        generated = await self._script_writer.generate(request)
        timeline = self._build_timeline(request, generated)

        if self._llm:
            try:
                structured = await self._llm.structured_completion(
                    instructions=INSTAGRAM_SYSTEM_PROMPT,
                    user_prompt=director_prompt(request, generated, generated.script),
                    response_model=InstagramReelsResponse,
                )
                return self._merge(generated, structured, self._enrich_timeline(timeline))
            except Exception:
                pass

        return self._merge(generated, InstagramReelsResponse(), self._enrich_timeline(timeline))

    def _build_timeline(self, request: InstagramDirectReelRequest, generated: InstagramReelsResponse) -> list[ReelSceneBeat]:
        timeline = list(generated.script.scene_by_scene_direction or generated.second_by_second_timeline)
        if timeline:
            return timeline
        return [
            ReelSceneBeat(
                second_range="0-3",
                scene=request.brief,
                camera_direction="tight close-up",
                emotional_intent="curiosity",
                retention_note="The hook must interrupt the scroll immediately.",
            )
        ]

    @staticmethod
    def _merge(base: InstagramReelsResponse, overlay: InstagramReelsResponse, timeline: list[ReelSceneBeat]) -> InstagramReelsResponse:
        data = base.model_dump(mode="json")
        overlay_data = overlay.model_dump(exclude_unset=True, mode="json")
        for key, value in overlay_data.items():
            if value not in (None, "", [], {}):
                data[key] = value
        data["second_by_second_timeline"] = timeline
        data["full_script"] = timeline
        data["retention_critical_moments"] = [f"{item.second_range}: {item.retention_note}" for item in timeline if item.interruption_pattern or "hook" in item.scene.lower()][:8]
        data["dopamine_spikes"] = [f"{item.second_range}: {item.scene}" for item in timeline if item.emotional_intent.lower() in {"surprise", "relief", "urgency", "confidence", "curiosity"}][:8]
        data["interruption_pattern_moments"] = [item.second_range for item in timeline if item.interruption_pattern][:8]
        notes = data.get("director_notes") or []
        if not notes:
            notes = [
                "Prioritize the first 2 seconds with a strong visual interruption.",
                "Use text resets every 2-4 seconds to sustain retention.",
                "Sync transition cuts with audio accents to increase replayability.",
            ]
        data["director_notes"] = notes
        return InstagramReelsResponse.model_validate(data)

    @staticmethod
    def _enrich_timeline(timeline: list[ReelSceneBeat]) -> list[ReelSceneBeat]:
        enriched: list[ReelSceneBeat] = []
        for idx, beat in enumerate(timeline):
            beat_data = beat.model_dump(mode="json")
            if not beat_data.get("transition_timing"):
                beat_data["transition_timing"] = "0.35s" if idx % 2 == 0 else "0.5s"
            if not beat_data.get("facial_expression"):
                beat_data["facial_expression"] = "high-energy and direct" if idx == 0 else "confident and intentional"
            if not beat_data.get("sound_design"):
                beat_data["sound_design"] = ["rhythmic hit", "ambient rise"]
            enriched.append(ReelSceneBeat.model_validate(beat_data))
        return enriched
