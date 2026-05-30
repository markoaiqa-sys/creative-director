# Creative Director Agent - V1 Supervisor Integration Quick Start

## What You Got

Your creative-director service is now supervisor-compatible. It exposes two endpoints:

```
GET  /health                    ← Render health probe + supervisor discovery
POST /execute                   ← Global supervisor calls this to request creative strategy
```

## Using the Service

### Health Check (For Render)
```bash
curl https://creative-director.onrender.com/health
```

Response:
```json
{
  "status": "ok",
  "service": "creative_director_agent",
  "version": "1.0.0"
}
```

### Execute Creative Strategy (From Supervisor)
```bash
curl -X POST https://creative-director.onrender.com/execute \
  -H "Content-Type: application/json" \
  -d '{
    "trace_id": "trace-abc123",
    "run_id": "run-xyz789",
    "session_id": "session-user-456",
    "user_input": {
      "message": "Generate compelling hooks for a SaaS product",
      "request_type": "creative_strategy"
    },
    "context": {
      "user_id": "user-123",
      "organization_id": "org-456",
      "workspace_id": "workspace-789",
      "onboarding": {
        "brand_name": "MyApp",
        "target_audience": "B2B marketers"
      }
    },
    "task": null,
    "contract_version": "1.0.0"
  }'
```

Response:
```json
{
  "agent_name": "creative_director_agent",
  "status": "ok",
  "insights": [
    {
      "id": "36cf30dc5ab7",
      "type": "hook_opportunity",
      "description": "Strong emotional appeal potential with target audience",
      "impact": 85.0,
      "confidence": 0.92,
      "sources": ["hook_generator"],
      "details": {
        "hook_types": ["curiosity", "social_proof"]
      }
    }
  ],
  "opportunities": [
    {
      "id": "a1b2c3d4e5f6",
      "type": "messaging_improvement",
      "description": "Add social proof elements to messaging",
      "recommendation": "Incorporate customer testimonials and case studies",
      "impact": 78.0,
      "confidence": 0.88,
      "effort": "medium",
      "sources": ["angle_generator"],
      "details": {}
    }
  ],
  "impact": 81.5,
  "confidence": 0.9,
  "sources": ["hook_generator", "angle_generator"],
  "error": null,
  "timestamp": "2026-05-30T15:23:45.123456Z",
  "execution_time_ms": 1234,
  "version": "1.0.0"
}
```

## How It Works Internally

1. **Request arrives** → `/execute` endpoint receives supervisor payload
2. **Trace ID stored** → Logs include `trace_id`, `run_id`, `session_id` for trace joining
3. **Task routing** → Keywords in message route to specific services:
   - "hook" → hook_generator
   - "copy" → ad_copy_generator  
   - "visual" → visual_concept_generator
   - "angle" → angle_generator
   - "reel|video|instagram" → instagram_engine
   - "trend|competitor" → trend_detector
   - "score" → scoring_service
4. **Service execution** → Internal services run (currently mock, to be integrated)
5. **Serialization** → Results converted to V1 contract format
6. **Response** → Always returns valid packet (never HTTP 500)

## Key Concepts

### Trace Propagation
The supervisor sends unique identifiers that must appear in all logs:
```python
log.info("step_name trace_id=%s run_id=%s session_id=%s", 
         trace_id, run_id, session_id)
```

This enables trace joining in log aggregators like Supabase or Datadog.

### Deterministic IDs
Every insight/opportunity gets a stable ID based on its type and description:
```python
insight_id = sha1("hook_opportunity|Strong emotional appeal potential"[:12])
# Same input always produces: 36cf30dc5ab7
```

This ensures idempotency - same request produces same response.

### Value Ranges
- **impact**: 0-100 (clipped to valid range)
- **confidence**: 0-1 (clipped to valid range)
- **sources**: List of service names (never empty)

### Error Handling
The endpoint NEVER returns HTTP 500. Even on failure, it returns a valid packet:
```json
{
  "agent_name": "creative_director_agent",
  "status": "failed",
  "insights": [],
  "opportunities": [],
  "impact": 0.0,
  "confidence": 0.0,
  "sources": ["creative_director_agent"],
  "error": {
    "type": "timeout",
    "code": "AGENT_TIMEOUT",
    "message": "Execution exceeded 30s timeout",
    "details": {}
  },
  "timestamp": "2026-05-30T15:23:45.123456Z",
  "execution_time_ms": 30000,
  "version": "1.0.0"
}
```

## File Structure

```
app/
  api/
    contracts.py                 ← V1 contract models
    routes/
      execute.py               ← /execute and /health endpoints
  services/
    task_router.py              ← Routes requests to services
    integration_serializer.py    ← Converts results to V1 format
  main.py                        ← Updated with execute_router
```

## Testing

Run HTTP tests:
```bash
python test_integration_http.py
```

Run unit tests (slow due to FastAPI startup):
```bash
pytest test_execute_endpoint.py -v
```

## Connecting the Real Engine

The `run_internal_orchestration()` function currently returns mock data.
To integrate with the real creative engine:

```python
# In app/api/routes/execute.py

async def run_internal_orchestration(...):
    # Import the real engine
    from app.services.engine import CreativeDirectorEngine
    
    # Get engine from service container
    engine = app.state.container.creative_director_engine
    
    # Call real services based on routing
    insights = []
    opportunities = []
    
    if "hook_generator" in services:
        hooks = await engine._hook_generator.generate(input_data)
        # Convert to insight dicts and extend insights
    
    if "ad_copy_generator" in services:
        copies = await engine._ad_copy_generator.generate(input_data)
        # Convert to opportunity dicts and extend opportunities
    
    # ... repeat for other services
    
    return {
        "insights": insights,
        "opportunities": opportunities,
    }
```

## Supervisor Configuration

Once deployed, configure on the global supervisor:

```yaml
# Environment variables on supervisor
CREATIVE_DIRECTOR_SERVICE_URL=https://creative-director.onrender.com

# In supervisor's agent registry
agents:
  creative_director_agent:
    service_url: ${CREATIVE_DIRECTOR_SERVICE_URL}
    health_path: /health
    contract_version: "1.0.0"
    timeout_seconds: 30
```

## Troubleshooting

**Service returns "status: failed"**
- Check `error.code` in response for details
- Common codes: EMPTY_INPUT, INTERNAL_ERROR, AGENT_TIMEOUT

**Logs not showing up in aggregator**
- Verify trace_id, run_id, session_id appear in log lines
- Check log formatting matches: "message trace_id=%s run_id=%s session_id=%s"

**Service times out**
- Increase DEFAULT_TIMEOUT_SECONDS in app/api/routes/execute.py
- Optimize run_internal_orchestration() implementation

**Mock data appears instead of real results**
- run_internal_orchestration() needs real engine integration
- See "Connecting the Real Engine" section above

## Support

See full documentation in:
- [supervisor_integration.md](/memories/repo/supervisor_integration.md)
- [SUPERVISOR_INTEGRATION_CHECKLIST.md](SUPERVISOR_INTEGRATION_CHECKLIST.md)
- Prompt 3 specification (Marko AI V1)
