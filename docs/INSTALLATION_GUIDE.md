# Neural Forge Installation Guide

## 🎯 **Installation Options**

Choose the installation method that best fits your needs:

### **Option 1: MCP Server (Recommended)**
Full Neural Forge with MCP server integration for Windsurf/Cursor.

### **Option 2: Memory-Only Integration**
Legacy approach using Windsurf memories directory (limited functionality).

---

## 🚀 **Option 1: MCP Server Installation**

### **Prerequisites**
- Python 3.12+
- Docker & Docker Compose
- Git

### **Step 1: Clone Repository**
```bash
git clone https://github.com/infinri/neural-forge.git
cd neural-forge
```

### **Step 2: Setup Environment**
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -U pip
pip install -r requirements.txt
```

### **Step 3: Bootstrap Stack**
```bash
# Interactive setup (recommended)
scripts/bootstrap.sh

# This will:
# 1. Generate .env file with credentials
# 2. Start Docker Compose stack (PostgreSQL, Prometheus, Grafana)
# 3. Run Alembic database migrations inside the Docker network
# 4. Start MCP server
# 5. Print Windsurf configuration snippet
```

### **Step 4: Configure Windsurf**
Add the printed configuration to `~/.codeium/windsurf/mcp_config.json`:

```json
{
"mcpServers": {
    "neural-forge": {
      "serverUrl": "http://127.0.0.1:8081/sse?token=<your-unique-token>"
    }
  }
}
```
Use the token printed by the bootstrap script (or the value you exported as `MCP_TOKEN`).

### **Step 5: Verify Installation**
```bash
# Test server
curl "http://127.0.0.1:8081/sse?token=$MCP_TOKEN"

# Should return: event: ready
```

**✅ Installation Complete!** All 12 Neural Forge tools are now available in Windsurf.

---

## 📁 **Option 2: Memory-Only Integration (Legacy)**

### **Step 1: Clone Repository**
```bash
git clone https://github.com/infinri/neural-forge.git
```

### **Step 2: Copy to Windsurf Memories**
```bash
cp -r neural-forge "/home/<your-username>/.codeium/windsurf/memories/Neural Forge"
```

### **Step 3: Get Global Rules**
- Copy global rules from: https://gist.github.com/infinri/2c50f85026807312eaf7305568bafe49
- Save as `/home/<your-username>/.codeium/windsurf/memories/global_rules.md`

### **Step 4: Customize Configuration**
- Edit `global_rules.md` to update file paths with your username
- Change AI name to your preferred name
- Verify all paths point to your actual directories

### **Step 5: Project Integration (Optional)**
- Copy local rules from: https://gist.github.com/infinri/e698ed08f10d8ca8ec9fb99203d7a265
- Paste into `.windsurfrules` file in your project root

**⚠️ Note:** This method provides limited functionality compared to the MCP server approach.

---

## 🔧 **Manual Setup (Advanced)**

### **Database Setup**
```bash
# Start PostgreSQL only
docker compose up -d postgres

# Run migrations inside Docker (recommended)
make db-upgrade-docker

# Or run migrations on host (sync driver)
export ALEMBIC_DATABASE_URL='postgresql+psycopg://forge:forge@localhost:55432/neural_forge'
alembic upgrade head
```

### **Server Setup**
```bash
# Set environment variables
export MCP_TOKEN=$(openssl rand -hex 32)
export DATABASE_URL='postgresql+asyncpg://forge:forge@localhost:55432/neural_forge'

# Start server
python -m server.main
```

### **Observability Stack (Optional)**
```bash
# Start Prometheus and Grafana
docker compose up -d prometheus grafana

# Access:
# Prometheus: http://127.0.0.1:9090
# Grafana: http://127.0.0.1:3000 (anonymous login)
```

---

## 🧪 **Development Setup**

### **Additional Dependencies**
```bash
# Install development dependencies
pip install -e .
pip install pytest pytest-asyncio pytest-cov ruff mypy

# Or use the dev requirements
pip install -r requirements-dev.txt  # if exists
```

### **Run Tests**
```bash
make test           # Run all tests
make test-coverage  # Run with coverage report
make lint          # Lint code
make typecheck     # Type checking
```

### **Database Development**
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations (inside Docker recommended)
make db-upgrade-docker

# Rollback migration
make db-downgrade
```

---

## 🔍 **Troubleshooting**

### **Common Issues**

**Port Already in Use**
```bash
# Check what's using port 8081
lsof -i :8081

# Kill process if needed
kill -9 <PID>
```

**Database Connection Failed**
```bash
# Check PostgreSQL status
docker compose ps postgres

# View PostgreSQL logs
docker compose logs postgres

# Reset database
docker compose down -v
docker compose up -d postgres
make db-upgrade-docker
```

**Windsurf Not Connecting**
1. Verify MCP config syntax in `~/.codeium/windsurf/mcp_config.json`
2. Check server is running: `curl "http://127.0.0.1:8081/sse?token=$MCP_TOKEN"`
3. Restart Windsurf after config changes
4. Check for duplicate server entries in config

**Python Environment Issues**
```bash
# Recreate virtual environment
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### **Getting Help**

1. Check server logs: `docker compose logs server`
2. Review installation steps above
3. Verify all prerequisites are installed
4. Check GitHub issues: https://github.com/infinri/neural-forge/issues

---

## 📚 **Next Steps**

After installation:

1. **Read the MCP Server Guide**: `docs/MCP_SERVER_GUIDE.md`
2. **Explore the Architecture**: `ARCHITECTURE_SUMMARY.md`
3. **Review Engineering Rules**: `memory/tags/` directory
4. **Check Cognitive Engine**: `cognitive-engine.md`
5. **Browse Navigation Guide**: `BIBLE_NAVIGATION.md`

**🎉 Welcome to Neural Forge!** You now have access to 63 engineering principles and autonomous rule application.
