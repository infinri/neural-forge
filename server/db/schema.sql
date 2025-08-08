-- Neural Forge MCP Server - Minimal SQLite schema (v1.3 baseline)
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Memory entries
CREATE TABLE IF NOT EXISTS memory_entries (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata JSON,
  quarantined INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_memory_project_created ON memory_entries(project_id, created_at);

-- Tasks queue
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  status TEXT NOT NULL, -- queued|in_progress|done|failed
  payload JSON,
  result JSON,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);

-- Code diffs saved by tools
CREATE TABLE IF NOT EXISTS diffs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  diff TEXT NOT NULL,
  author TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_diffs_project_created ON diffs(project_id, created_at);

-- Logged errors
CREATE TABLE IF NOT EXISTS errors (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  level TEXT NOT NULL, -- info|warn|error
  message TEXT NOT NULL,
  context JSON,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_errors_level_created ON errors(level, created_at);

