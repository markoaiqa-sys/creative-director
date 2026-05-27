from collections import Counter
import re

from app.models import NormalizedReelData, ReelAnalysisCategory, ReelInsight, ReelReference


class ViralPatternEngine:
    def build_insights(self, *, brief: str, references: list[ReelReference], normalized_reels: list[NormalizedReelData] | None = None, niche: str | None = None, audience: str | None = None) -> list[ReelInsight]:
        sources = self._collect_sources(brief, references, normalized_reels or [])
        token_counts = Counter(self._tokens(" ".join(sources)))
        top_keywords = [token for token, _ in token_counts.most_common(12)]
        opening_line = self._best_opening_line(sources)
        visual_hook = self._best_visual_hook(sources)
        cta_style = self._best_cta_style(sources)
        caption_pattern = self._caption_pattern(sources)
        emotion = self._emotional_trigger(sources)
        pacing = self._pacing_style(sources)
        scene_density = self._scene_density(sources)
        audio_trend = self._audio_trend(references)
        transition_pattern = self._transition_pattern(sources)
        competitor_pattern = self._competitor_pattern(references)

        return [
            ReelInsight(category=ReelAnalysisCategory.VISUAL_HOOK, insight=visual_hook[0], why_it_works=visual_hook[1], evidence=top_keywords[:3], score=86, recommendation="Turn the product or promise into a visual interruption in the first frame."),
            ReelInsight(category=ReelAnalysisCategory.OPENING_LINE, insight=opening_line[0], why_it_works=opening_line[1], evidence=top_keywords[:3], score=91, recommendation="Lead with the problem, contradiction, or outcome before any setup."),
            ReelInsight(category=ReelAnalysisCategory.EMOTIONAL_TRIGGER, insight=emotion[0], why_it_works=emotion[1], evidence=top_keywords[:4], score=84, recommendation="Anchor the script in one dominant feeling and keep the emotional arc tight."),
            ReelInsight(category=ReelAnalysisCategory.PACING_STYLE, insight=pacing[0], why_it_works=pacing[1], evidence=top_keywords[:4], score=82, recommendation="Use fast scene changes before the first value beat, then slow slightly for payoff."),
            ReelInsight(category=ReelAnalysisCategory.SCENE_DENSITY, insight=scene_density[0], why_it_works=scene_density[1], evidence=top_keywords[:5], score=78, recommendation="Keep each scene doing one job: hook, proof, payoff, or CTA."),
            ReelInsight(category=ReelAnalysisCategory.CTA_STYLE, insight=cta_style[0], why_it_works=cta_style[1], evidence=top_keywords[:3], score=80, recommendation="Make the CTA match the friction level of the audience and the offer."),
            ReelInsight(category=ReelAnalysisCategory.CAPTION_PATTERN, insight=caption_pattern[0], why_it_works=caption_pattern[1], evidence=top_keywords[:3], score=79, recommendation="Use the caption to extend the curiosity loop rather than repeat the reel."),
            ReelInsight(category=ReelAnalysisCategory.AUDIO_TREND, insight=audio_trend[0], why_it_works=audio_trend[1], evidence=[reference.audio_name for reference in references if reference.audio_name][:3], score=73, recommendation="Match the sound energy to the retention curve and the emotional promise."),
            ReelInsight(category=ReelAnalysisCategory.TRANSITION_PATTERN, insight=transition_pattern[0], why_it_works=transition_pattern[1], evidence=top_keywords[:3], score=77, recommendation="Use interruptions and visual resets to prevent attention collapse."),
            ReelInsight(category=ReelAnalysisCategory.COMPETITOR_PATTERN, insight=competitor_pattern[0], why_it_works=competitor_pattern[1], evidence=[reference.username or reference.reel_url or "source" for reference in references[:3]], score=85, recommendation="Borrow the repeatable structure, not the surface copy."),
        ]

    def build_hook_alternatives(self, brief: str, audience: str | None = None, niche: str | None = None) -> list[str]:
        audience_text = audience or niche or "this audience"
        topic = brief.rstrip(".")
        return [
            f"Why {audience_text} are still missing {topic}.",
            f"The fastest way to fix {topic.lower()} is not what most creators use.",
            f"If {audience_text} only watch one reel this week, make it this one.",
        ]

    def build_reusable_formulas(self, insights: list[ReelInsight]) -> list[str]:
        formulas = [
            "Problem interrupt -> proof -> payoff -> CTA",
            "Contrarian opening -> fast reset -> visual proof -> saved CTA",
            "Outcome first -> stepwise reveal -> emotional relief -> comment CTA",
        ]
        if any(insight.category == ReelAnalysisCategory.COMPETITOR_PATTERN for insight in insights):
            formulas.insert(0, "Competitor framing -> sharper contrast -> quick proof -> direct CTA")
        return formulas[:4]

    def build_content_gaps(self, references: list[ReelReference]) -> list[str]:
        caption_text = " ".join([reference.caption or "" for reference in references]).lower()
        gaps: list[str] = []
        if "social proof" not in caption_text and "testimonial" not in caption_text:
            gaps.append("Little visible social proof angle")
        if "behind the scenes" not in caption_text and "process" not in caption_text:
            gaps.append("Weak process or BTS storytelling")
        if "comparison" not in caption_text and "vs" not in caption_text:
            gaps.append("Few direct comparison-style hooks")
        if not gaps:
            gaps.append("No obvious content gap from the provided references")
        return gaps

    def _collect_sources(self, brief: str, references: list[ReelReference], normalized_reels: list[NormalizedReelData]) -> list[str]:
        sources = [brief]
        for reference in references:
            sources.extend([reference.caption or "", reference.transcript or "", reference.username or "", reference.reel_url or ""])
            sources.extend(reference.comments)
        for reel in normalized_reels:
            sources.extend([reel.caption or "", reel.transcript or "", reel.username or reel.competitor_name or "", reel.reel_url or ""])
            sources.extend(reel.comments)
        return [source for source in sources if source]

    def _best_opening_line(self, sources: list[str]) -> tuple[str, str]:
        joined = " ".join(sources).lower()
        if any(token in joined for token in ["secret", "mistake", "stop", "don't", "wrong"]):
            return "Opening line uses a contradiction or warning.", "This pattern creates instant curiosity and forces the viewer to keep watching for the fix."
        return "Opening line leads with the outcome before the explanation.", "Outcome-first openings reduce cognitive load and accelerate watch-through."

    def _best_visual_hook(self, sources: list[str]) -> tuple[str, str]:
        joined = " ".join(sources).lower()
        if any(token in joined for token in ["before", "after", "split", "transformation"]):
            return "Visual hook uses a clear before-and-after contrast.", "Transformational visuals are immediately legible and create a retention promise."
        return "Visual hook uses a hard frame reset in the first second.", "A surprising object, gesture, or text block interrupts scrolling and buys attention."

    def _best_cta_style(self, sources: list[str]) -> tuple[str, str]:
        joined = " ".join(sources).lower()
        if any(token in joined for token in ["save", "comment", "follow"]):
            return "CTA leans on lightweight engagement and saves.", "Low-friction CTAs maintain momentum and increase post-view action."
        return "CTA asks for the next step with a direct action.", "Direct CTAs reduce ambiguity and connect the reel to the conversion path."

    def _caption_pattern(self, sources: list[str]) -> tuple[str, str]:
        joined = " ".join(sources).lower()
        if any(token in joined for token in ["part 1", "part 2", "thread"]):
            return "Caption uses a continuation loop or serial structure.", "Sequential framing helps comments and replay behavior."
        return "Caption extends the hook without overexplaining.", "Short captions preserve curiosity while the reel carries the main message."

    def _emotional_trigger(self, sources: list[str]) -> tuple[str, str]:
        joined = " ".join(sources).lower()
        if any(token in joined for token in ["relief", "save time", "faster"]):
            return "Primary emotional trigger is relief and speed.", "Relief is powerful in short-form because it promises an easier path forward."
        return "Primary emotional trigger is curiosity and contrast.", "Curiosity keeps viewers locked in until the payoff resolves the gap."

    def _pacing_style(self, sources: list[str]) -> tuple[str, str]:
        joined = " ".join(sources).lower()
        if any(token in joined for token in ["fast", "quick cut", "jump cut"]):
            return "Fast-paced opening with brief resets.", "Rapid pacing buys attention early and then uses resets to prevent drop-off."
        return "Measured pacing with a clear first beat and faster payoff.", "Controlled pacing helps the audience track the promise before the proof lands."

    def _scene_density(self, sources: list[str]) -> tuple[str, str]:
        count = len([source for source in sources if source])
        if count >= 4:
            return "High scene density with multiple proof beats.", "Dense scene changes reduce boredom and increase visible progress."
        return "Compact scene density with one idea per beat.", "Simple scene structure prevents overload and keeps retention stable."

    def _audio_trend(self, references: list[ReelReference]) -> tuple[str, str]:
        if any(reference.audio_name for reference in references):
            return "Audio trend is tied to a named or repeated sound.", "Repeated sounds create memory cues and make the reel feel culturally current."
        return "Audio trend is implied by pacing rather than a specific track.", "When no sound is provided, rhythm and cuts carry most of the trend signal."

    def _transition_pattern(self, sources: list[str]) -> tuple[str, str]:
        joined = " ".join(sources).lower()
        if any(token in joined for token in ["cut", "jump", "transition", "swap"]):
            return "Transition pattern uses deliberate jump cuts and resets.", "Visual resets keep the reel from feeling static."
        return "Transition pattern relies on abrupt text and camera changes.", "Interruptions are the core mechanism for stopping swipe-away behavior."

    def _competitor_pattern(self, references: list[ReelReference]) -> tuple[str, str]:
        if references:
            return "Competitor pattern repeats the same hook frame and payoff structure.", "Consistency across winning reels usually points to a repeatable, transferable structure."
        return "Competitor pattern is inferred from the niche rather than direct reel samples.", "When explicit competitor reels are absent, strong niche patterns still inform the structure."

    @staticmethod
    def _tokens(value: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", value.lower())