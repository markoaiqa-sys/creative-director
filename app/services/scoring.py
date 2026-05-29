import math
import re
from collections import Counter

from app.models import (
    AdCopy,
    CreativeInput,
    CreativeScore,
    GeneratedCreative,
    LLMCreativeEvaluation,
    Platform,
    VisualConcept,
)
from app.providers.groq_llm import GroqLLMProvider
from app.services.prompts import PLATFORM_ASPECT_RATIOS, PLATFORM_COPY_LIMITS, CREATIVE_SYSTEM_PROMPT, scoring_prompt

EMOTION_WORDS = {
    "secret",
    "mistake",
    "waste",
    "struggle",
    "double",
    "unlock",
    "finally",
    "stuck",
    "faster",
    "better",
    "easy",
    "win",
    "growth",
    "save",
    "stop",
}


class CreativeScoringService:
    def __init__(self, llm: GroqLLMProvider | None = None) -> None:
        self._llm = llm

    async def score(
        self,
        payload: CreativeInput,
        concepts: list[VisualConcept],
        ad_copies: list[AdCopy],
        generated_creatives: list[GeneratedCreative],
    ) -> list[CreativeScore]:
        import asyncio
        copy_lookup = {(copy.hook_text, copy.angle_name): copy for copy in ad_copies}
        generated_lookup = {creative.concept_id: creative for creative in generated_creatives}
        token_frequency = Counter(
            token
            for copy in ad_copies
            for token in self._tokens(" ".join([copy.primary_text, copy.headline, copy.description]))
        )

        concept_copy_pairs = []
        eval_tasks = []
        for concept in concepts:
            copy = copy_lookup.get((concept.hook_text, concept.angle_name)) or self._fallback_copy(concept=concept, ad_copies=ad_copies)
            concept_copy_pairs.append((concept, copy))
            eval_tasks.append(self._llm_evaluate(payload=payload, concept=concept, copy=copy))

        llm_evals = await asyncio.gather(*eval_tasks)

        scores: list[CreativeScore] = []
        for i, (concept, copy) in enumerate(concept_copy_pairs):
            generated = generated_lookup.get(concept.concept_id)
            heuristic = self._heuristic_scores(payload=payload, copy=copy, concept=concept, generated=generated, token_frequency=token_frequency)
            llm_eval = llm_evals[i]

            clarity = self._blend_scores(heuristic["clarity"], llm_eval.clarity)
            platform_fit = self._blend_scores(heuristic["platform_fit"], llm_eval.platform_fit)
            persuasion = llm_eval.persuasion
            cta_alignment = llm_eval.cta_alignment
            uniqueness = heuristic["uniqueness"]
            emotional_intensity = heuristic["emotional_intensity"]

            total = round(
                clarity * 0.22
                + persuasion * 0.24
                + cta_alignment * 0.18
                + platform_fit * 0.18
                + uniqueness * 0.10
                + emotional_intensity * 0.08
            )
            scores.append(
                CreativeScore(
                    concept_id=concept.concept_id,
                    emotional_intensity=emotional_intensity,
                    clarity=clarity,
                    uniqueness=uniqueness,
                    platform_fit=platform_fit,
                    persuasion=persuasion,
                    cta_alignment=cta_alignment,
                    total_score=min(100, max(0, total)),
                    rationale=llm_eval.rationale,
                )
            )

        ranked = sorted(scores, key=lambda item: item.total_score, reverse=True)
        for index, item in enumerate(ranked, start=1):
            item.rank = index
        return ranked

    async def score_ad_copies(
        self,
        payload: CreativeInput,
        concepts: list[VisualConcept],
        ad_copies: list[AdCopy],
        generated_creatives: list[GeneratedCreative],
        scored_creatives: list[CreativeScore] | None = None,
    ) -> list[AdCopy]:
        if not ad_copies:
            return []

        if scored_creatives is None:
            scored_creatives = await self.score(payload, concepts, ad_copies, generated_creatives)
        score_lookup = {item.concept_id: item for item in scored_creatives}

        scored: list[AdCopy] = []
        for copy in ad_copies:
            concept = self._match_concept(copy=copy, concepts=concepts)
            score = score_lookup.get(concept.concept_id) if concept else None
            scored.append(
                copy.model_copy(
                    update={
                        "total_score": score.total_score if score else 0,
                        "score_rank": score.rank if score else None,
                        "score_rationale": score.rationale if score else "No score available.",
                    }
                )
            )
        return scored

    async def _llm_evaluate(
        self,
        *,
        payload: CreativeInput,
        concept: VisualConcept,
        copy: AdCopy,
    ) -> LLMCreativeEvaluation:
        if not self._llm:
            return LLMCreativeEvaluation(
                clarity=70,
                persuasion=68,
                cta_alignment=72,
                platform_fit=70,
                rationale="Heuristic review used for clarity, platform fit, and CTA alignment.",
            )

        try:
            return await self._llm.structured_completion(
                instructions=CREATIVE_SYSTEM_PROMPT,
                user_prompt=scoring_prompt(
                    payload,
                    concept,
                    {
                        "primary_text": copy.primary_text,
                        "headline": copy.headline,
                        "description": copy.description,
                        "cta": copy.cta,
                    },
                ),
                response_model=LLMCreativeEvaluation,
            )
        except Exception as exc:
            print(f"[WARN] CreativeScoringService heuristic fallback: {type(exc).__name__}: {exc}")
            return LLMCreativeEvaluation(
                clarity=70,
                persuasion=68,
                cta_alignment=72,
                platform_fit=70,
                rationale="Heuristic review used while model scoring was temporarily unavailable.",
            )

    def _heuristic_scores(
        self,
        *,
        payload: CreativeInput,
        copy: AdCopy,
        concept: VisualConcept,
        generated: GeneratedCreative | None,
        token_frequency: Counter[str],
    ) -> dict[str, int]:
        return {
            "emotional_intensity": self._score_emotion(copy=copy, concept=concept),
            "clarity": self._score_clarity(payload.platform, copy),
            "uniqueness": self._score_uniqueness(copy, token_frequency),
            "platform_fit": self._score_platform_fit(payload.platform, copy, concept, generated),
        }

    @staticmethod
    def _blend_scores(heuristic: int, llm_value: int) -> int:
        return round((heuristic * 0.35) + (llm_value * 0.65))

    def _fallback_copy(self, *, concept: VisualConcept, ad_copies: list[AdCopy]) -> AdCopy:
        for copy in ad_copies:
            if copy.angle_name == concept.angle_name:
                return copy
        return ad_copies[0]

    def _match_concept(self, *, copy: AdCopy, concepts: list[VisualConcept]) -> VisualConcept | None:
        for concept in concepts:
            if concept.hook_text == copy.hook_text and concept.angle_name == copy.angle_name:
                return concept
        for concept in concepts:
            if concept.angle_name == copy.angle_name:
                return concept
        for concept in concepts:
            if concept.hook_text == copy.hook_text:
                return concept
        return concepts[0] if concepts else None

    def _score_emotion(self, *, copy: AdCopy, concept: VisualConcept) -> int:
        text = " ".join([copy.primary_text, copy.headline, concept.mood, concept.scene_description]).lower()
        hits = sum(1 for token in self._tokens(text) if token in EMOTION_WORDS)
        punctuation_bonus = 4 if "!" in copy.primary_text or "!" in copy.headline else 0
        return min(100, 48 + hits * 8 + punctuation_bonus)

    def _score_clarity(self, platform: Platform, copy: AdCopy) -> int:
        limits = PLATFORM_COPY_LIMITS[platform]
        penalties = 0
        if len(copy.primary_text) > limits["primary_text"]:
            penalties += 25
        if len(copy.headline) > limits["headline"]:
            penalties += 25
        if len(copy.description) > limits["description"]:
            penalties += 20
        if len(copy.headline.split()) > 8:
            penalties += 8
        if len(copy.primary_text.split()) > 25:
            penalties += 8
        return max(45, 95 - penalties)

    def _score_uniqueness(self, copy: AdCopy, token_frequency: Counter[str]) -> int:
        tokens = self._tokens(" ".join([copy.primary_text, copy.headline, copy.description]))
        if not tokens:
            return 40
        rare_cutoff = max(1, math.ceil(len(token_frequency) * 0.02))
        rare_tokens = sum(1 for token in tokens if token_frequency[token] <= rare_cutoff)
        lexical_diversity = len(set(tokens)) / max(1, len(tokens))
        return min(100, round(50 + lexical_diversity * 35 + rare_tokens * 2))

    def _score_platform_fit(
        self,
        platform: Platform,
        copy: AdCopy,
        concept: VisualConcept,
        generated: GeneratedCreative | None,
    ) -> int:
        score = 60
        if concept.aspect_ratio in PLATFORM_ASPECT_RATIOS[platform]:
            score += 20
        if generated and generated.status.value == "generated":
            score += 10
        if platform == Platform.TIKTOK and concept.aspect_ratio == "9:16":
            score += 10
        if platform == Platform.GOOGLE and len(copy.headline) <= 30:
            score += 5
        if platform == Platform.META and len(copy.primary_text) <= 125:
            score += 5
        return min(100, score)

    @staticmethod
    def _tokens(value: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", value.lower())
