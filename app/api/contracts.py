"""
V1 Agent Output Contract - Global Supervisor Integration.

This module defines the standardized request/response payloads that all agent
services must comply with for orchestration by the global Marko AI Supervisor.

See: orchestrator/src/graph/contract.py (global supervisor reference)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class UserInput(BaseModel):
    """User query and optional request type hint."""
    message: str
    request_type: Optional[str] = None


class ExecuteRequest(BaseModel):
    """
    Inbound payload from the global Marko AI Supervisor.
    Sent to POST /execute on every agent service call.
    """
    trace_id: str = Field(..., description="UUID for distributed tracing")
    run_id: str = Field(..., description="UUID for this supervisor execution")
    session_id: str = Field(..., description="UUID for user session")
    user_input: UserInput
    context: Dict[str, Any] = Field(default_factory=dict, description="Supervisor context: user_id, org_id, workspace_id, onboarding, etc.")
    task: Optional[str] = None
    contract_version: str = Field(default="1.0.0")


class Insight(BaseModel):
    """
    Finding discovered by the agent service.
    Deterministic ID ensures same insight always gets the same ID.
    """
    id: str = Field(..., description="Deterministic: sha1(type|description)[:12]")
    type: str = Field(..., description="Snake_case category e.g. 'missing_title_tag'")
    description: str = Field(..., description="Human-readable finding")
    impact: float = Field(..., ge=0.0, le=100.0, description="0-100 scale")
    confidence: float = Field(..., ge=0.0, le=1.0, description="0-1 scale")
    sources: List[str] = Field(..., description="Tools/data that produced this")
    details: Dict[str, Any] = Field(default_factory=dict, description="Optional extra structured data")


class Opportunity(BaseModel):
    """
    Actionable recommendation from the agent service.
    Deterministic ID ensures same opportunity always gets the same ID.
    """
    id: str = Field(..., description="Deterministic: sha1(type|description)[:12]")
    type: str = Field(..., description="Snake_case category")
    description: str = Field(..., description="Human-readable finding")
    recommendation: str = Field(..., description="Specific action to take")
    impact: float = Field(..., ge=0.0, le=100.0, description="0-100 scale")
    confidence: float = Field(..., ge=0.0, le=1.0, description="0-1 scale")
    sources: List[str] = Field(..., description="Tools/data that produced this")
    effort: str = Field(..., description="'low' | 'medium' | 'high'")
    details: Dict[str, Any] = Field(default_factory=dict, description="Optional extra structured data")


class ErrorInfo(BaseModel):
    """Error envelope returned when status != 'ok'."""
    type: str = Field(..., description="'timeout' | 'service_error' | 'validation_error' | 'empty_result'")
    code: str = Field(..., description="Machine-readable code e.g. 'AGENT_TIMEOUT'")
    message: str = Field(..., description="Human-readable error message")
    details: Dict[str, Any] = Field(default_factory=dict)


class AgentOutputContract(BaseModel):
    """
    Outbound packet returned by POST /execute.
    The global supervisor validates all agent responses against this schema.
    """
    # Identity
    agent_name: str = Field(..., description="Canonical name: 'creative_director_agent'")
    status: str = Field(..., description="'ok' | 'timeout' | 'failed'")

    # When status == "ok" - all fields populated
    insights: List[Insight] = Field(default_factory=list)
    opportunities: List[Opportunity] = Field(default_factory=list)
    impact: float = Field(..., ge=0.0, le=100.0, description="Overall service-level impact 0-100")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall service-level confidence 0-1")
    sources: List[str] = Field(..., description="All internal data sources used (never empty)")
    error: Optional[ErrorInfo] = None

    # Metadata
    timestamp: str = Field(..., description="ISO-8601 timestamp")
    execution_time_ms: int = Field(..., ge=0, description="Total execution time in milliseconds")
    version: str = Field(default="1.0.0")


class HealthResponse(BaseModel):
    """Response from GET /health endpoint."""
    status: str = Field(..., description="'ok' | 'degraded' | 'down'")
    service: str = Field(..., description="Service name")
    version: str = Field(default="1.0.0")
