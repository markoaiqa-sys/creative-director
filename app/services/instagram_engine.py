from app.models import (
    InstagramAnalyzeCompetitorRequest,
    InstagramAnalyzeReelRequest,
    InstagramDetectTrendsRequest,
    InstagramDirectReelRequest,
    InstagramGenerateScriptRequest,
    InstagramReelsResponse,
    InstagramScoreReelRequest,
)
from app.services.instagram_analyzer import InstagramAnalyzer
from app.services.reels_director import ReelsDirector
from app.services.retention_scorer import RetentionScorer
from app.services.script_writer import ScriptWriter
from app.services.trend_detector import TrendDetector
from app.services.viral_pattern_engine import ViralPatternEngine


class InstagramDirectorEngine:
    def __init__(
        self,
        *,
        trend_detector: TrendDetector,
        analyzer: InstagramAnalyzer,
        script_writer: ScriptWriter,
        director: ReelsDirector,
        scorer: RetentionScorer,
        pattern_engine: ViralPatternEngine,
    ) -> None:
        self._trend_detector = trend_detector
        self._analyzer = analyzer
        self._script_writer = script_writer
        self._director = director
        self._scorer = scorer
        self._pattern_engine = pattern_engine

    async def analyze_reel(self, request: InstagramAnalyzeReelRequest) -> InstagramReelsResponse:
        return await self._analyzer.analyze_reel(request)

    async def analyze_competitor(self, request: InstagramAnalyzeCompetitorRequest) -> InstagramReelsResponse:
        return await self._analyzer.analyze_competitor(request)

    async def detect_trends(self, request: InstagramDetectTrendsRequest) -> InstagramReelsResponse:
        response = await self._analyzer.analyze_reel(request)
        response.trend_objects = self._trend_detector.detect(
            brief=request.brief,
            trending_reels=request.trending_reels,
            competitor_reels=request.competitor_reels,
            normalized_reels=request.normalized_reels,
            niche=request.niche,
            audience=request.audience,
        )
        response.reusable_winning_formulas = self._pattern_engine.build_reusable_formulas(response.analysis)
        response.top_performing_patterns = response.reusable_winning_formulas
        response.content_gaps = self._pattern_engine.build_content_gaps(request.competitor_reels)
        return response

    async def generate_script(self, request: InstagramGenerateScriptRequest) -> InstagramReelsResponse:
        return await self._script_writer.generate(request)

    async def direct_reel(self, request: InstagramDirectReelRequest) -> InstagramReelsResponse:
        return await self._director.direct(request)

    async def score_reel(self, request: InstagramScoreReelRequest) -> InstagramReelsResponse:
        analysis = await self._analyzer.analyze_reel(request)
        trends = self._trend_detector.detect(
            brief=request.brief,
            trending_reels=request.trending_reels,
            competitor_reels=request.competitor_reels,
            normalized_reels=request.normalized_reels,
            niche=request.niche,
            audience=request.audience,
        )
        script = await self._script_writer.generate(request)
        score = self._scorer.score(request=request, analysis=analysis.analysis, trends=trends, script=script.script, normalized_reels=request.normalized_reels)
        response = script
        response.scores = score
        response.viral_probability_score = max(response.viral_probability_score, score.total_score)
        response.retention_score = score.retention
        return response