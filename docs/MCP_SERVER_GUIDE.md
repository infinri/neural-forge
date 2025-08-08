# Neural Forge MCP Server Guide

## 🚀 **MCP Server Overview**

The Neural Forge MCP server provides a JSON-RPC interface over Server-Sent Events (SSE) that exposes all Neural Forge capabilities to Windsurf, Cursor, and other MCP-compatible clients.

## 📋 **Available Tools**

### **Memory Operations**
- `add_memory` - Store new memories with tags and metadata
- `get_memory` - Retrieve specific memory by ID
- `search_memory` - Semantic search across stored memories

### **Governance & Rules**
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
MCP_TOKEN=dev                    # Authentication token
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5432/neural_forge

# Optional
MCP_DB_PATH=data/mcp.db         # SQLite fallback for tests
```

### **Windsurf Configuration**
Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "neural-forge": {
      "serverUrl": "http://127.0.0.1:8081/sse?token=dev"
    }
  }
}
```

## 🐳 **Docker Deployment**

### **Full Stack (Recommended)**
```bash
# Start PostgreSQL + MCP Server + Observability
docker compose up -d

# Services available:
# - MCP Server: http://127.0.0.1:8081
# - Prometheus: http://127.0.0.1:9090  
# - Grafana: http://127.0.0.1:3000
```

### **Server Only**
```bash
docker build -t neural-forge-mcp .
docker run --rm -p 8081:8080 \
  -e MCP_TOKEN=dev \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db \
  neural-forge-mcp
```

## 📊 **Observability**

### **Metrics (Prometheus)**
- `mcp_requests_total{endpoint}` - Total requests per endpoint
- `mcp_errors_total{endpoint,code}` - Total errors per endpoint
- `mcp_request_duration_seconds{endpoint}` - Request duration histogram

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
# Run migrations
make db-upgrade

# Check current migration
make db-current

# Rollback one migration
make db-downgrade
```

### **SQLite (Testing)**
Automatically used when `DATABASE_URL` is not set. Database file location controlled by `MCP_DB_PATH`.

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

## 🔍 **Troubleshooting**

### **Connection Issues**
```bash
# Test server health
curl http://127.0.0.1:8081/sse?token=dev

# Check server logs
docker compose logs neural-forge-server

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
make db-upgrade
```

### **Authentication Issues**
- Ensure `MCP_TOKEN` matches between server and client config
- Token can be passed via `Authorization: Bearer <token>` header or `?token=<token>` query parameter

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
  -H "Authorization: Bearer dev" \
  -H "Content-Type: application/json" \
  -d '{"content": "Memory content", "tags": ["tag1"]}'

# Search memories  
curl -X POST http://127.0.0.1:8081/search_memory \
  -H "Authorization: Bearer dev" \
  -H "Content-Type: application/json" \
  -d '{"query": "search terms", "limit": 10}'
```
