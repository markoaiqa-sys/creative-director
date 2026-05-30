"""
Execute Endpoint - Global Supervisor Integration.

Exposes the standardized POST /execute and GET /health endpoints
that allow the global Marko AI Supervisor to call and discover this service.
"""

import asyncio
import logging
from time import perf_counter
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.api.contracts import ExecuteRequest, HealthResponse, AgentOutputContract
from app.services.integration_serializer import (
    serialize_error_response,
    serialize_to_v1,
)
from app.services.task_router import route_task

router = APIRouter(tags=["supervisor-integration"])
log = logging.getLogger("execute")

AGENT_NAME = "creative_director_agent"
DEFAULT_TIMEOUT_SECONDS = 30.0


@router.get("/health")
async def health() -> HealthResponse:
    """
    Health check endpoint required by Render health probes and supervisor discovery.

    Returns:
        Service status and version info.
    """
    return HealthResponse(
        status="ok",
        service=AGENT_NAME,
        version="1.0.0",
    )


@router.post("/execute")
async def execute(request: ExecuteRequest) -> Dict[str, Any]:
    """
    Entry point called by the global Marko AI Supervisor.

    This endpoint:
      1. Receives a standardized ExecuteRequest with trace_id, run_id, session_id
      2. Routes the request to appropriate internal services
      3. Aggregates results into a V1 AgentOutputContract packet
      4. Returns the packet (never raises HTTP 500)

    Args:
        request: The supervisor execution request

    Returns:
        AgentOutputContract as a dict (ready for JSON serialization)
    """
    started = perf_counter()

    # Log incoming request with trace identifiers
    log.info(
        "execute called trace_id=%s run_id=%s session_id=%s task=%s",
        request.trace_id,
        request.run_id,
        request.session_id,
        request.task or "auto",
    )

    try:
        # Step 1: Validate and extract request
        message = request.user_input.message or ""
        if not message.strip():
            log.warning(
                "execute called with empty message trace_id=%s run_id=%s",
                request.trace_id,
                request.run_id,
            )
            return serialize_error_response(
                agent_name=AGENT_NAME,
                error_type="validation_error",
                error_code="EMPTY_INPUT",
                error_message="user_input.message is empty or missing",
                started_at=started,
                error_details={"field": "user_input.message"},
            ).model_dump()

        # Step 2: Route to internal services
        services = route_task(request)
        log.info(
            "routed to services trace_id=%s run_id=%s services=%s",
            request.trace_id,
            request.run_id,
            services,
        )

        # Step 3: Run internal orchestration
        # For now, return a mock success response with example insights/opportunities
        # In a real implementation, this would call the actual engine and orchestrate services
        internal_result = await run_internal_orchestration(
            trace_id=request.trace_id,
            run_id=request.run_id,
            session_id=request.session_id,
            message=message,
            services=services,
            context=request.context,
        )

        # Step 4: Serialize to V1 contract
        output = serialize_to_v1(
            agent_name=AGENT_NAME,
            internal_result=internal_result,
            services_used=services,
            started_at=started,
        )

        log.info(
            "execute completed trace_id=%s run_id=%s status=%s insights=%d opportunities=%d",
            request.trace_id,
            request.run_id,
            output.status,
            len(output.insights),
            len(output.opportunities),
        )

        return output.model_dump()

    except asyncio.TimeoutError:
        log.error(
            "execute timeout trace_id=%s run_id=%s",
            request.trace_id,
            request.run_id,
        )
        return serialize_error_response(
            agent_name=AGENT_NAME,
            error_type="timeout",
            error_code="AGENT_TIMEOUT",
            error_message=f"Execution exceeded {DEFAULT_TIMEOUT_SECONDS}s timeout",
            started_at=started,
        ).model_dump()

    except ValidationError as e:
        log.error(
            "execute validation error trace_id=%s run_id=%s error=%s",
            request.trace_id,
            request.run_id,
            str(e),
        )
        return serialize_error_response(
            agent_name=AGENT_NAME,
            error_type="validation_error",
            error_code="INVALID_REQUEST",
            error_message=f"Request validation failed: {str(e)[:200]}",
            started_at=started,
        ).model_dump()

    except Exception as exc:
        log.error(
            "execute failed trace_id=%s run_id=%s error=%s",
            request.trace_id,
            request.run_id,
            str(exc),
            exc_info=True,
        )
        return serialize_error_response(
            agent_name=AGENT_NAME,
            error_type="service_error",
            error_code="INTERNAL_ERROR",
            error_message=f"Internal service error: {str(exc)[:200]}",
            started_at=started,
        ).model_dump()


async def run_internal_orchestration(
    trace_id: str,
    run_id: str,
    session_id: str,
    message: str,
    services: list[str],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run the internal service orchestration.

    This is where the agent's business logic lives. For now, this returns a mock
    success response. In production, this would:
      1. Call the appropriate services from app.services
      2. Aggregate their results
      3. Perform any additional analysis or scoring
      4. Return structured insights and opportunities

    Args:
        trace_id: Distributed trace ID from supervisor
        run_id: Execution run ID from supervisor
        session_id: User session ID from supervisor
        message: The user's creative request message
        services: List of internal service names to execute
        context: Supervisor context (user_id, org_id, workspace_id, onboarding, etc.)

    Returns:
        Dict with 'insights' and 'opportunities' keys (as lists of dicts)
    """
    log.info(
        "starting internal orchestration trace_id=%s run_id=%s services=%s",
        trace_id,
        run_id,
        services,
    )

    # TODO: Integrate with actual engine and services
    # This is a placeholder that demonstrates the expected output structure
    # In production:
    #   - Call app.services.engine.CreativeDirectorEngine
    #   - Run instagram_engine, trend_detector, etc. as needed
    #   - Aggregate their outputs
    #   - Return structured insights and opportunities

    insights = [
        {
            "type": "creative_opportunity_identified",
            "description": f"Generated creative strategy for: {message}",
            "impact": 75.0,
            "confidence": 0.85,
            "sources": services,
            "details": {
                "message_processed": message,
                "services_used": services,
            },
        }
    ]

    opportunities = [
        {
            "type": "hook_optimization",
            "description": "Consider adding emotional hooks to capture attention",
            "recommendation": "Develop 5 hook variations focused on curiosity and social proof",
            "impact": 80.0,
            "confidence": 0.9,
            "effort": "low",
            "sources": services,
            "details": {
                "hook_types": ["curiosity", "social_proof"],
            },
        },
        {
            "type": "visual_improvement",
            "description": "Visual concepts should emphasize brand colors and modern aesthetic",
            "recommendation": "Generate 5 visual concepts with emphasis on brand identity",
            "impact": 70.0,
            "confidence": 0.8,
            "effort": "medium",
            "sources": services,
            "details": {
                "style_notes": "modern, minimalist, brand-aligned",
            },
        },
    ]

    return {
        "insights": insights,
        "opportunities": opportunities,
        "metadata": {
            "trace_id": trace_id,
            "run_id": run_id,
            "session_id": session_id,
            "services_executed": services,
            "user_id": context.get("user_id"),
            "organization_id": context.get("organization_id"),
        },
    }
