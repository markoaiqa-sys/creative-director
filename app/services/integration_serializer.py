"""
Integration Serializer - Converts internal service results to V1 Agent Output Contract.

This is the only place where internal data shapes are translated into the global contract.
Every insight and opportunity gets a deterministic ID based on its type and description.
"""

import hashlib
import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, List, Optional

from app.api.contracts import (
    AgentOutputContract,
    ErrorInfo,
    Insight,
    Opportunity,
)

log = logging.getLogger("integration_serializer")


def make_id(item_type: str, description: str) -> str:
    """
    Generate a deterministic ID for an insight or opportunity.
    Same input always produces the same ID.
    
    Args:
        item_type: The type field (e.g., "missing_hook", "improve_copy")
        description: The description field
    
    Returns:
        First 12 characters of SHA1 hash
    """
    raw = f"{item_type}|{description}".lower().encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def clip(value: float, min_val: float, max_val: float) -> float:
    """Clip a value to the range [min_val, max_val]."""
    return max(min_val, min(max_val, float(value)))


def utc_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def serialize_to_v1(
    agent_name: str,
    internal_result: Dict[str, Any],
    services_used: List[str],
    started_at: float,
) -> AgentOutputContract:
    """
    Convert service internal result format to the V1 Agent Output Contract.

    This function extracts insights and opportunities from the internal result,
    applies deterministic ID generation, normalizes values to valid ranges,
    and returns a properly formatted V1 packet.

    Args:
        agent_name: The canonical agent name (e.g., "creative_director_agent")
        internal_result: The result dict from running internal services
        services_used: List of service names that were executed
        started_at: perf_counter() timestamp from start of execution

    Returns:
        A fully populated AgentOutputContract ready for the global supervisor
    """
    insights: List[Insight] = []
    opportunities: List[Opportunity] = []

    try:
        # Extract insights from internal result
        # The internal structure may vary by service, so this is a flexible adapter
        raw_insights = internal_result.get("insights", [])
        if isinstance(raw_insights, list):
            for item in raw_insights:
                if isinstance(item, dict):
                    insight = Insight(
                        id=make_id(item.get("type", "insight"), item.get("description", "")),
                        type=item.get("type", "creative_insight"),
                        description=item.get("description", ""),
                        impact=clip(float(item.get("impact", 50.0)), 0.0, 100.0),
                        confidence=clip(float(item.get("confidence", 0.7)), 0.0, 1.0),
                        sources=item.get("sources", services_used or [agent_name]),
                        details=item.get("details", {}),
                    )
                    insights.append(insight)

        # Extract opportunities from internal result
        raw_opportunities = internal_result.get("opportunities", [])
        if isinstance(raw_opportunities, list):
            for item in raw_opportunities:
                if isinstance(item, dict):
                    opportunity = Opportunity(
                        id=make_id(item.get("type", "opportunity"), item.get("description", "")),
                        type=item.get("type", "optimization_opportunity"),
                        description=item.get("description", ""),
                        recommendation=item.get("recommendation", ""),
                        impact=clip(float(item.get("impact", 50.0)), 0.0, 100.0),
                        confidence=clip(float(item.get("confidence", 0.7)), 0.0, 1.0),
                        sources=item.get("sources", services_used or [agent_name]),
                        effort=item.get("effort", "medium"),
                        details=item.get("details", {}),
                    )
                    opportunities.append(opportunity)

    except Exception as e:
        log.error(f"Error extracting insights/opportunities: {e}", exc_info=True)

    # Calculate aggregate impact and confidence
    all_items = insights + opportunities
    if all_items:
        all_impacts = [item.impact for item in all_items]
        all_confidences = [item.confidence for item in all_items]
        avg_impact = sum(all_impacts) / len(all_impacts) if all_impacts else 0.0
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
    else:
        avg_impact = 0.0
        avg_confidence = 0.0

    # Determine overall status
    has_output = bool(insights or opportunities)
    status = "ok" if has_output else "failed"
    error = None

    if not has_output:
        error = ErrorInfo(
            type="empty_result",
            code="NO_OUTPUT_PRODUCED",
            message="Service ran but produced no insights or opportunities.",
            details={},
        )

    # Build final contract packet
    sources = services_used if services_used else [agent_name]
    execution_time_ms = int((perf_counter() - started_at) * 1000)

    return AgentOutputContract(
        agent_name=agent_name,
        status=status,
        insights=insights,
        opportunities=opportunities,
        impact=clip(avg_impact, 0.0, 100.0),
        confidence=clip(avg_confidence, 0.0, 1.0),
        sources=sources,
        error=error,
        timestamp=utc_now(),
        execution_time_ms=execution_time_ms,
        version="1.0.0",
    )


def serialize_error_response(
    agent_name: str,
    error_type: str,
    error_code: str,
    error_message: str,
    started_at: float,
    error_details: Optional[Dict[str, Any]] = None,
) -> AgentOutputContract:
    """
    Create a properly formatted error response packet.

    Args:
        agent_name: The canonical agent name
        error_type: 'timeout' | 'service_error' | 'validation_error'
        error_code: Machine-readable code (e.g., 'AGENT_TIMEOUT')
        error_message: Human-readable error message
        started_at: perf_counter() timestamp from start
        error_details: Optional dict with additional error context

    Returns:
        An AgentOutputContract with status='failed'
    """
    execution_time_ms = int((perf_counter() - started_at) * 1000)

    return AgentOutputContract(
        agent_name=agent_name,
        status="failed",
        insights=[],
        opportunities=[],
        impact=0.0,
        confidence=0.0,
        sources=[agent_name],
        error=ErrorInfo(
            type=error_type,
            code=error_code,
            message=error_message,
            details=error_details or {},
        ),
        timestamp=utc_now(),
        execution_time_ms=execution_time_ms,
        version="1.0.0",
    )
