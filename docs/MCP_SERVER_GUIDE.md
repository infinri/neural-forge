# Neural Forge MCP Server Guide

## 🚀 **MCP Server Overview**

The Neural Forge MCP server provides a JSON-RPC interface over Server-Sent Events (SSE) that exposes all Neural Forge capabilities to Windsurf, Cursor, and other MCP-compatible clients.

## 📋 **Available Tools**

### **Memory Operations**
- `add_memory` - Store new memories with tags and metadata
- `get_memory` - Retrieve specific memory by ID
- `search_memory` - Semantic search across stored memories

### **Governance & Rules**
- `activate_governance` - **NEW**: Autonomous pre-action governance analysis for AI planning/coding activities
- `get_governance_policies` - Retrieve governance policies from memory/*.rules.yml
- `get_active_tokens` - Get all 63 active engineering tokens from memory/tags/*
- `get_rules` - Get specific rule categories and their content

### **Task Management**
- `enqueue_task` - Add new tasks to the processing queue
- `get_next_task` - Retrieve next pending task
- `update_task_status` - Update task status (pending, in_progress, completed, failed)

### **Code Tracking**
- `save_diff` - Save code diffs with metadata for tracking changes
- `list_recent` - List recent diffs, memories, or tasks

### **Logging**
- `log_error` - Log errors with context and metadata

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Required
# Generate once: `openssl rand -hex 32`
MCP_TOKEN=<your-unique-token>     # Authentication token shared with clients
# Optional: bypass placeholder enforcement for local debugging only (never use in prod)
# ALLOW_INSECURE_DEV=true

# App (async driver)
# If using Docker Compose Postgres from host, use port 55432
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:55432/neural_forge

# Alembic (sync driver) — used only when running migrations on host
ALEMBIC_DATABASE_URL=postgresql+psycopg://forge:forge@localhost:55432/neural_forge

# Legacy compatibility (off by default; enable only if older clients require `?token=` auth)
# MCP_ALLOW_QUERY_TOKEN=false
```

### **Windsurf Configuration**
Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
"mcpServers": {
    "neural-forge": {
      "serverUrl": "http://127.0.0.1:8081/sse?token=<your-unique-token>"
    }
  }
}
```

## 🐳 **Docker Deployment**

### **Full Stack (Recommended)**
```bash
# Generate (or export) a token once per environment
export MCP_TOKEN=$(openssl rand -hex 32)

# Start PostgreSQL + MCP Server + Observability
docker compose up -d

# Services available:
# - MCP Server: http://127.0.0.1:8081
# - Prometheus: http://127.0.0.1:9090  
# - Grafana: http://127.0.0.1:3000
```
Migrations run automatically via the `migrate` service inside the Compose network. The `server` service waits until migrations complete successfully.

### **Server Only**
```bash
TOKEN=$(openssl rand -hex 32)
docker build -t neural-forge-mcp .
docker run --rm -p 8081:8080 \
  -e MCP_TOKEN=$TOKEN \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db \
  neural-forge-mcp
```

If the server starts without `MCP_TOKEN`, or with a placeholder such as `dev`/`change-me`, startup logs
`startup.placeholder_token_blocked` and exits. For local experiments only, set `ALLOW_INSECURE_DEV=true` to acknowledge the
risk and allow placeholder tokens.

## 📊 **Observability**

### **Metrics (Prometheus)**
- `mcp_requests_total{endpoint}` - Total requests per endpoint
- `mcp_errors_total{endpoint,code}` - Total errors per endpoint
- `mcp_request_duration_seconds{endpoint}` - Request duration histogram
  
Event/handler metrics:
- `events_published_total{type}` - Total events published by type
- `events_consumed_total{type}` - Total events successfully consumed by handlers
- `event_handler_errors_total{type}` - Total handler errors observed by the EventBus
- `orchestrator_handler_errors_total{type}` - Total handler errors inside orchestrator handlers

### **Tracing (OpenTelemetry)**

Tracing defaults to ON in dev when `TRACING_ENABLED` is unset; otherwise OFF. To enable or override:

```bash
export TRACING_ENABLED=true
# Use OTLP HTTP exporter if available; falls back to console exporter
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4318/v1/traces
# or (fallback)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
# Optional headers (comma-separated)
export OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer mytoken
# Optional resource details
export OTEL_SERVICE_NAME=neural-forge-mcp
export OTEL_RESOURCE_ATTRIBUTES=region=us-east-1,team=forge
```

Health exposes tracing and DB status for quick checks:

```bash
curl http://127.0.0.1:8081/health | jq
```

Example fields:

```json
{
  "serverVersion": "1.x.y",
  "orchestratorRunning": true,
  "tracing": {
    "enabled": true,
    "initialized": true,
    "exporter": "otlp_http"
  },
  "db": {"backend": "postgresql", "status": "up"},
  "status": "ok"
}
```

Spans:
- HTTP requests via FastAPI instrumentation
- Domain spans: `EventBus.publish` and `Orchestrator.handle`
- Errors mark spans with status=ERROR and record exceptions
- Span links connect orchestrator spans to originating HTTP request via `traceparent`

### **Structured Logging**
JSON logs with fields:
- `endpoint` - MCP tool endpoint called
- `requestId` - Unique request identifier
- `elapsedMs` - Request duration in milliseconds
- `status` - Success/error status
- `error` - Error details (if applicable)

## 🗄️ **Database**

### **PostgreSQL (Production)**
```bash
# Run migrations inside Docker (recommended)
make db-upgrade-docker

# Check current migration
make db-current

# Rollback one migration
make db-downgrade
```
Host-based migrations (optional):
```bash
export ALEMBIC_DATABASE_URL=postgresql+psycopg://forge:forge@127.0.0.1:55432/neural_forge
alembic upgrade head
```

### **SQLite (Removed)**
SQLite support has been removed. PostgreSQL is required and `DATABASE_URL` must be set.

## 🧪 **Testing**

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Lint and type check
make lint
make typecheck
```

## **Troubleshooting**

### **Connection Issues**
```bash
# Test server health
curl "http://127.0.0.1:8081/sse?token=$MCP_TOKEN"

# Check health endpoint (no auth required)
curl http://127.0.0.1:8081/health

# Check server logs
docker compose logs server

# Verify Windsurf config
cat ~/.codeium/windsurf/mcp_config.json
```

### **Database Issues**
```bash
# Check PostgreSQL connection
docker compose exec postgres psql -U forge -d neural_forge -c "\dt"

# Reset database
docker compose down -v
docker compose up -d
make db-upgrade-docker
```

### **Authentication Issues**
- Ensure `MCP_TOKEN` matches between server and client config
- Requests must include `Authorization: Bearer <token>` header (legacy `?token=` query auth is disabled by default; set `MCP_ALLOW_QUERY_TOKEN=true` only if you must support older clients)

## 📚 **API Reference**

### **MCP JSON-RPC Protocol**
```json
// Initialize connection
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {"protocolVersion": "2024-11-05"},
  "id": 1
}

// List available tools
{
  "jsonrpc": "2.0", 
  "method": "tools/list",
  "id": 2
}

// Call a tool
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "add_memory",
    "arguments": {
      "content": "Important memory to store",
      "tags": ["engineering", "best-practice"]
    }
  },
  "id": 3
}
```

### **Direct HTTP API**
All tools are also available as direct HTTP endpoints:
```bash
# Add memory
curl -X POST http://127.0.0.1:8081/add_memory \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Memory content", "tags": ["tag1"]}'

# Search memories
curl -X POST http://127.0.0.1:8081/search_memory \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "search terms", "limit": 10}'
```

#### Admin Endpoints (Diagnostics)

Require `Authorization: Bearer <MCP_TOKEN>`

- `GET /admin/stats`
  - Optional: `projectId`
  - Returns counts for `memory_entries`, `diffs`, `errors`, and `tasks` (queued, inProgress, done, failed, total)
  - Example:
    ```bash
    curl -s "http://127.0.0.1:8081/admin/stats?projectId=nf" -H "Authorization: Bearer $MCP_TOKEN" | jq
    ```

- `GET /admin/memory_meta`
  - Optional: `projectId`, `quarantinedOnly`
  - Pagination: `limit` (default 100, max 500), `offset` (default 0)
  - Returns memory metadata only: `id`, `projectId`, `quarantined`, `createdAt`, `size`
  - Example:
    ```bash
    curl -s "http://127.0.0.1:8081/admin/memory_meta?projectId=nf&quarantinedOnly=true&limit=50" -H "Authorization: Bearer $MCP_TOKEN" | jq
    ```

## 🧠 **Autonomous Pre-Action Governance**

### **Overview**

The `activate_governance` tool is Neural Forge's flagship feature that automatically analyzes AI conversations to detect engineering activities and provides relevant guidance **before** implementation begins.

### **How It Works**

1. **Context Detection**: Analyzes user messages for engineering activities (API design, security, database design, etc.)
2. **Confidence Scoring**: Assigns confidence levels to detected activities (0-100%)
3. **Rule Retrieval**: Dynamically loads relevant governance rules from Neural Forge memory/tags
4. **Guidance Synthesis**: Formats actionable recommendations with priority warnings
5. **Seamless Integration**: Returns structured guidance for AI planning processes

### **Tool Schema**

```json
{
  "name": "activate_governance",
  "description": "Activate pre-action governance analysis for AI planning/coding activities",
  "inputSchema": {
    "type": "object",
    "properties": {
      "user_message": {"type": "string"},
      "conversation_history": {"type": "array", "items": {"type": "string"}},
      "force_activation": {"type": "boolean"}
    },
    "required": ["user_message"]
  }
}
```

### **Example Usage**

#### **MCP JSON-RPC Call**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "activate_governance",
    "arguments": {
      "user_message": "I want to build a secure REST API with authentication",
      "conversation_history": ["I'm starting a new web project", "It needs to handle user data"]
    }
  },
  "id": 1
}
```

#### **Response**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "governance_activated": true,
    "guidance": "🧠 **NEURAL FORGE GOVERNANCE ACTIVATED**\n\n**Activity Detected:** Api Design\n**Confidence:** 40.0%\n\n**Summary:** For Api Design activities, 10 relevant governance rules apply.\n\n**⚠️ Important Warnings:**\n⚠️ API design detected - ensure proper authentication and input validation\n\n**Recommendation:** Apply these governance principles during planning and implementation.",
    "message": "Neural Forge governance activated - apply these principles during planning and implementation",
    "timestamp": "2025-08-08T21:16:08.483505Z"
  },
  "id": 1
}
```

#### **HTTP API Call**
```bash
curl -X POST "http://127.0.0.1:8080/tool/activate_governance" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -d '{
    "user_message": "I want to build a secure REST API with authentication"
  }'
```

### **Activation Scenarios**

The governance system automatically activates for these engineering activities:

- **API Design**: REST APIs, GraphQL, authentication systems
- **Security Implementation**: Authentication, authorization, input validation
- **Database Design**: Schema design, data modeling, migrations
- **Architecture Planning**: Microservices, system design, scalability
- **Performance Optimization**: Caching, algorithms, bottlenecks
- **Code Refactoring**: Clean code, SOLID principles, maintainability
- **Testing Strategy**: Unit tests, integration tests, test automation
- **Deployment**: CI/CD, containerization, production deployment

### **Configuration**

- **Activation Threshold**: 10% confidence minimum (configurable)
- **Rule Sources**: Loads from `memory/tags/*` directory
- **Response Time**: Typically <10ms for governance analysis
- **Token Integration**: Uses all 63 Neural Forge engineering tokens
