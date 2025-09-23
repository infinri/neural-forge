-- Neural Forge MCP Server - PostgreSQL schema (v1.3 baseline)

-- Memory entries
CREATE TABLE IF NOT EXISTS memory_entries (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata JSONB,
  quarantined BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memory_project_created ON memory_entries(project_id, created_at);

-- Tasks queue
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL, -- queued|in_progress|done|failed
  payload JSONB,
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);

-- Code diffs saved by tools
CREATE TABLE IF NOT EXISTS diffs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  diff TEXT NOT NULL,
  author TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_diffs_project_created ON diffs(project_id, created_at);

-- Logged errors
CREATE TABLE IF NOT EXISTS errors (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  level TEXT NOT NULL, -- info|warn|error
  message TEXT NOT NULL,
  context JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_errors_level_created ON errors(level, created_at);

-- Governance token effectiveness metrics
CREATE TABLE IF NOT EXISTS governance_token_metrics (
  token_id TEXT NOT NULL,
  project_id TEXT NOT NULL DEFAULT 'global',
  activation_count INTEGER NOT NULL DEFAULT 0,
  effectiveness_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  last_applied_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (token_id, project_id)
);
CREATE INDEX IF NOT EXISTS idx_token_metrics_project_updated ON governance_token_metrics(project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_metrics_activation ON governance_token_metrics(activation_count DESC);
