# Neural Forge 🧠⚡

## ⚠️ **Work in Progress**

Neural Forge started as a simple YAML rule framework and has evolved into an AI engineering system that functions as an MCP server with PostgreSQL persistence and autonomous rule application.

**Current Status:**
- ✅ **MCP Server**: Neural Forge IS a complete MCP server with 12 tools for Windsurf/Cursor
- ✅ **Rule Framework**: 63 engineering tokens across 8 categories  
- ✅ **Infrastructure**: Docker, PostgreSQL, CI/CD, observability
- 🚧 **Pre-Action Governance**: Autonomous rule activation before AI planning (in development)
- 🚧 **Cross-Session Learning**: Token effectiveness tracking and adaptation (planned)

---

Neural Forge is an MCP server that provides autonomous AI engineering intelligence for Windsurf/Cursor integration.

## 🌟 **Key Features**

- **🔄 Infrastructure**: PostgreSQL persistence, Docker deployment, CI/CD pipeline
- **⚡ Simple Setup**: Works after setup with Windsurf
- **🧠 Autonomous Operation**: Rule application without manual prompting
- **🎯 Context Detection**: Attempts to detect engineering scenarios
- **🔗 Cross-Domain Links**: Connects security, performance, architecture, testing
- **📊 Comprehensive Coverage**: 63 engineering tokens across 8 major categories

## 🎯 **What is Neural Forge?**

Neural Forge is a complete MCP (Model Context Protocol) server that provides:

- **🧠 Autonomous Engineering Intelligence**: 63 token-compressed rules that activate automatically based on context
- **⚡ Full MCP Protocol**: Complete JSON-RPC implementation with 12 tools exposed to Windsurf/Cursor
- **🔄 PostgreSQL Persistence**: Database with async SQLAlchemy and Alembic migrations
- **🌐 Comprehensive Coverage**: Security, performance, architecture, testing, AI learning, and more
- **🎯 Context-Aware Activation**: Automatically detects engineering scenarios and applies relevant best practices

## 🏗️ **System Architecture**

### Three-Layer Intelligent Architecture

```bash
┌─────────────────────────────────────────────────────────────┐
│                    GOVERNANCE LAYER                         │
│              (global_rules.md - Pure Policies)              │
├─────────────────────────────────────────────────────────────┤
│                  INTELLIGENCE LAYER                         │
│           (Neural Forge - 63 Optimized Tokens)              │
│     • Associative Memory    • Cascading Activation          │
│     • Context Recognition   • Cross-Domain Links            │
├─────────────────────────────────────────────────────────────┤
│                   PROJECT LAYER                             │
│              (.localrules - Project Constraints)            │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 **Key Features**

### 🧠 **Human-Like Associative Memory**

- **Cascading Activation**: Primary tokens trigger related tokens across categories
- **Strength-Based Prioritization**: Associative strength values (0.7-0.9) determine activation
- **Context Weighting**: Usage frequency and success rates influence token selection
- **Cross-Domain Links**: Security tokens connect to performance, architecture, and testing

### ⚡ **Autonomous Operation**

- **Silent Enforcement**: Applies engineering principles without explicit prompting
- **Context Recognition**: Automatically detects API development, data processing, testing scenarios
- **Intelligent Activation**: Uses semantic triggers and keyword matching
- **Pattern Learning**: Creates new tokens for novel successful patterns

### 📊 **Comprehensive Knowledge Base**

| Category         | Tokens | Focus Areas                                          |
|------------------|--------|------------------------------------------------------|
| **Security**     | 10     | OAuth2/JWT, encryption, threat modeling, zero trust  |
| **Code Quality** | 9      | SOLID, DRY, refactoring, technical debt management   |
| **AI Learning**  | 13     | Cognitive patterns, self-improvement, fractal MCP    |
| **Architecture** | 8      | Microservices, event sourcing, DDD, cloud-native     |
| **Performance**  | 6      | Algorithm complexity, caching, memory optimization   |
| **Reliability**  | 8      | Error handling, circuit breakers, chaos engineering  |
| **Data**         | 4      | Database design, privacy compliance, migrations      |
| **Testing**      | 5      | Advanced testing, performance testing, automation    |
| **TOTAL**        | **63** | **Complete engineering coverage**                    |

## 🎯 **How It Works**

### 1. **Context Recognition**

```yaml
api_development:
  triggers: ["endpoint", "route", "API", "service"]
  primary_activation: ["APIDesignPrinciples", "InputSanitization", "AuthBypassPrevention"]
  cascading_pattern:
    - APIDesignPrinciples → MicroservicesPatterns, EventSourcingCQRS
    - InputSanitization → SecurityHeaders, ThreatModel
    - AuthBypassPrevention → ZeroTrustArchitecture, OAuth2JWTPatterns
```

### 2. **Associative Activation**

```yaml
activation_algorithm:
  primary_threshold: 0.7  # Minimum strength for activation
  cascading_rules:
    - strength_0.9+: "cascade_to_all_direct_links"
    - strength_0.8-0.89: "cascade_to_top_3_links"
    - strength_0.7-0.79: "cascade_to_top_2_links"
  context_weighting:
    - usage_frequency: 1.2x multiplier
    - success_context: 1.3x multiplier
```

### 3. **Learning & Adaptation**

```yaml
learning_mechanisms:
  usage_tracking: "Monitor token activation frequency and success"
  strength_calibration: "Adjust associations based on effectiveness"
  pattern_recognition: "Identify successful token combinations"
  cross_session_memory: "Preserve learning across sessions"
```

## 📁 **Project Structure**

See the full, authoritative layout in `ARCHITECTURE_SUMMARY.md`.

## 🔧 **Token Architecture**

Tokens are YAML-based, with linked tags and usage metadata. For details and the associative model, see:
- `cognitive-engine.md` (how tokens are parsed/applied)
- `BIBLE_NAVIGATION.md` (canonical index and associative mappings)

## 🚀 **Quick Start**

### **1. Clone and Setup**

```bash
git clone https://github.com/infinri/neural-forge.git
cd neural-forge

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### **2. Start MCP Server**

```bash
# Interactive bootstrap (recommended)
scripts/bootstrap.sh

# Manual setup
docker compose up -d
make db-upgrade
python -m server.main
```

### **3. Connect to Windsurf**

Add to your `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "neural-forge": {
      "serverUrl": "http://127.0.0.1:8081/sse?token=dev"
    }
  }
}
```

### **4. Verify Connection**

```bash
# Test server
curl http://127.0.0.1:8081/sse?token=dev

# Test tools in Windsurf
# All 12 Neural Forge tools should be available
```

## 🛠️ **Available Tools**

Neural Forge exposes 12 tools via the MCP interface:

### **Memory Operations**
- `add_memory` - Store memories with tags and metadata
- `get_memory` - Retrieve specific memory by ID  
- `search_memory` - Semantic search across stored memories

### **Governance & Rules**
- `get_governance_policies` - Retrieve governance policies
- `get_active_tokens` - Get all 63 active engineering tokens
- `get_rules` - Get specific rule categories

### **Task Management**
- `enqueue_task` - Add tasks to processing queue
- `get_next_task` - Retrieve next pending task
- `update_task_status` - Update task status

### **Code Tracking & Logging**
- `save_diff` - Save code diffs with metadata
- `list_recent` - List recent diffs/memories/tasks
- `log_error` - Log errors with context

## 📚 **Documentation**

- **[Installation Guide](docs/INSTALLATION_GUIDE.md)** - Complete setup instructions
- **[MCP Server Guide](docs/MCP_SERVER_GUIDE.md)** - Server configuration and API reference
- **[Architecture Summary](ARCHITECTURE_SUMMARY.md)** - System architecture and design
- **[Cognitive Engine](cognitive-engine.md)** - How autonomous rule application works
- **[Bible Navigation](BIBLE_NAVIGATION.md)** - Master index of all engineering rules

## 🎯 **Auto-Activation**

Neural Forge automatically activates on every session:

```bash
1. LOAD: global_rules.md (governance policies)
2. READ: Neural Forge/ARCHITECTURE_SUMMARY.md
3. READ: Neural Forge/cognitive-engine.md  
4. SCAN: Neural Forge/memory/tags/ (63 tokens)
5. ACTIVATE: Associative memory + autonomous operation
```

### **Navigation**

- **Canonical Index**: `BIBLE_NAVIGATION.md` - Master navigation and associative mappings
- **Category Browse**: `memory/tags/{category}/README.md` - Category overviews
- **Token Details**: `memory/tags/{category}/{token}.yml` - Individual tokens

## 🎯 **Use Cases**

### **API Development**

- Automatically applies `APIDesignPrinciples`, `InputSanitization`, `AuthBypassPrevention`
- Cascades to `MicroservicesPatterns`, `OAuth2JWTPatterns`, `SecurityMonitoring`
- Ensures secure, scalable API architecture

### **Performance Optimization**

- Triggers `PerformanceMonitoring`, `CachingPatterns`, `AlgorithmComplexity`
- Connects to `IOOptimization`, `MemoryManagement`, `DatabaseDesign`
- Comprehensive performance engineering approach

### **Security Implementation**

- Activates `ThreatModel`, `EncryptionPatterns`, `ZeroTrustArchitecture`
- Links to `DataPrivacyCompliance`, `SecurityHeaders`, `InputSanitization`
- Complete security-first engineering

## 🧠 **Experimental Capabilities**

### **Associative Memory Approach**

- **Linked Concepts**: One concept can trigger related concepts through predefined associations
- **Context Sensitivity**: Different contexts are designed to activate different knowledge networks
- **Strength-Based Priority**: Associations have strength values to determine priority
- **Learning Framework**: Infrastructure for tracking successful patterns (not yet fully implemented)

### **Context-Aware Operation**

- **Background Processing**: Designed to work without explicit prompting
- **Context Detection**: Attempts to detect engineering scenarios through keyword matching
- **Cross-Domain Links**: Connects related concepts across different engineering domains
- **Learning Infrastructure**: Framework for improvement through usage (implementation in progress)

### **Adaptive Framework**

- **Usage Tracking**: Infrastructure for tracking token effectiveness (basic implementation)
- **Pattern Analysis**: Framework for identifying successful engineering combinations
- **Strength Adjustment**: Mechanism for adjusting associative strengths (planned feature)
- **Pattern Evolution**: Structure for creating new tokens for emerging patterns (future work)

## 🏆 **Current Status**

✅ **63 Engineering Tokens** - Curated collection covering major software engineering domains  
✅ **Associative Architecture** - Basic implementation of linked concepts and cascading activation  
✅ **Context Recognition** - Framework for detecting engineering scenarios  
✅ **Cross-Domain Links** - Connections established between related engineering concepts  
🚧 **Learning System** - Infrastructure in place, full implementation pending  
🚧 **Testing & Validation** - System needs real-world testing to prove effectiveness  

## 🤝 **Contributing**

Contributions are welcome:

1. **Token Enhancement**: Improve existing engineering tokens or add new ones
2. **Associative Links**: Strengthen connections between related concepts  
3. **Usage Analytics**: Help improve effectiveness through usage data
4. **Pattern Recognition**: Identify new successful engineering patterns

## 📄 **License**

MIT License - See LICENSE file for details

## 🎯 **Vision**

Neural Forge is an experiment in creating more intelligent AI-assisted software engineering. The goal is to move beyond static rule lists toward a system that can contextually apply engineering knowledge.

**The hypothesis**: By implementing associative memory patterns and context recognition, AI systems can apply engineering principles more intelligently and learn from usage patterns.

---
