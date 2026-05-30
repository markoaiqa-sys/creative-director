"""
Task Router - Routes incoming supervisor requests to internal services.

Maps user queries and explicit task hints to internal service names.
This is entirely internal - the supervisor never sees these names.
"""

import logging
from typing import List
from app.api.contracts import ExecuteRequest

log = logging.getLogger("task_router")


def route_task(request: ExecuteRequest) -> List[str]:
    """
    Decide which internal services to invoke for this request.

    Priority:
      1. Explicit `task` field from global supervisor
      2. Keyword inference from user_input.message
      3. Default: full workflow with all primary services

    Returns:
        List of internal service identifiers to run.
    """
    # Priority 1: Explicit task hint from supervisor
    if request.task:
        return [request.task]

    # Priority 2: Infer from message keywords
    message = (request.user_input.message or "").lower()
    
    # Creative hooks, copywriting, messaging angles
    if any(keyword in message for keyword in ["hook", "opening", "attention", "grab"]):
        return ["hook_generator"]
    
    # Ad copy, headlines, body text
    if any(keyword in message for keyword in ["copy", "headline", "text", "message", "ad text"]):
        return ["ad_copy_generator"]
    
    # Visual concepts, design, imagery
    if any(keyword in message for keyword in ["visual", "concept", "design", "image", "style", "color"]):
        return ["visual_concept_generator"]
    
    # Messaging angles, emotional targeting
    if any(keyword in message for keyword in ["angle", "emotional", "appeal", "tone", "messaging"]):
        return ["angle_generator"]
    
    # Instagram reels, video scripts, viral patterns
    if any(keyword in message for keyword in ["reel", "video", "script", "instagram", "viral", "engagement"]):
        return ["instagram_engine"]
    
    # Competitive intelligence, trend detection
    if any(keyword in message for keyword in ["competitor", "trend", "market", "analysis", "insight"]):
        return ["trend_detector"]
    
    # Creative scoring, performance assessment
    if any(keyword in message for keyword in ["score", "performance", "retention", "effective"]):
        return ["scoring_service"]
    
    # Priority 3: Default to full workflow
    # Run all primary services for comprehensive creative strategy
    return [
        "hook_generator",
        "angle_generator",
        "ad_copy_generator",
        "visual_concept_generator",
        "instagram_engine",
        "trend_detector",
        "scoring_service",
    ]
