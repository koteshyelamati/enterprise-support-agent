# Enterprise Support Agent

An AI-powered IT support ticket resolution system built with a LangGraph agentic workflow (Python/FastAPI) and a Spring Boot ticket orchestration service.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client / curl                            │
└─────────────────────┬───────────────────────────────────────────┘
                      │ POST /api/v1/tickets/resolve
                      │ HTTP Basic Auth
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│               ticket-service  :8080  (Spring Boot 3)            │
│  TicketController → TicketOrchestrationService → WebClient      │
│  GlobalExceptionHandler (RFC 9457 ProblemDetail)                │
└─────────────────────┬───────────────────────────────────────────┘
                      │ POST /agent/resolve
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│               agent-core  :8000  (FastAPI + LangGraph)          │
│                                                                 │
│   ┌──────────────────────────────────────────────────────┐      │
│   │               LangGraph StateGraph                   │      │
│   │                                                      │      │
│   │  analyze_ticket ──[critical]──► escalate_human       │      │
│   │       │                                              │      │
│   │  query_vector_db ──[conf>0.75]──► resolve_ticket     │      │
│   │       │                                              │      │
│   │  fetch_external_api ──[found]──► resolve_ticket      │      │
│   │       │                                              │      │
│   │  self_correct ──[errors≥3]──► escalate_human         │      │
│   │       └──────────────────────► fetch_external_api    │      │
│   └──────────────────────────────────────────────────────┘      │
│                                                                 │
│   ChromaDB :8001  (20-entry IT knowledge base)                  │
└─────────────────────────────────────────────────────────────────┘
```

## Services

| Service | Port | Stack |
|---------|------|-------|
| agent-core | 8000 | Python 3.12, FastAPI, LangGraph, ChromaDB |
| ticket-service | 8080 | Java 17, Spring Boot 3.3, WebClient |
| chromadb | 8001 | ChromaDB vector database |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) OpenAI or Anthropic API key for real LLM responses

### 1. Clone and configure

```bash
git clone https://github.com/your-username/enterprise-support-agent.git
cd enterprise-support-agent
cp .env.example .env
```

### 2. Configure environment (optional)

Edit `.env` to set your LLM API key. Without one, the system runs in **mock mode** automatically:

```bash
# Use a real LLM
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...

# Force mock mode (default when no key is set)
MOCK_LLM=true
```

### 3. Start all services

```bash
docker compose up --build
```

Services start in dependency order: ChromaDB → agent-core (seeds KB) → ticket-service.

### 4. Verify health

```bash
curl http://localhost:8000/health           # agent-core
curl http://localhost:8080/actuator/health  # ticket-service (if actuator enabled)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (optional) |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (optional) |
| `MOCK_LLM` | `true` | Force mock LLM when no key is provided |
| `CHROMA_HOST` | `localhost` | ChromaDB hostname |
| `CHROMA_PORT` | `8001` | ChromaDB port |
| `APP_USERNAME` | `user` | HTTP Basic Auth username for ticket-service |
| `APP_PASSWORD` | `changeme-in-production` | HTTP Basic Auth password |
| `AGENT_CORE_URL` | `http://localhost:8000` | agent-core base URL (used by ticket-service) |

## API Usage

### Resolve a ticket

```bash
curl -X POST http://localhost:8080/api/v1/tickets/resolve \
  -u user:changeme-in-production \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TKT-001",
    "description": "User cannot connect to VPN from home office. Getting authentication error.",
    "priority": "high"
  }'
```

**Response:**

```json
{
  "ticket_id": "TKT-001",
  "resolution": "Reset VPN credentials and verify MFA token...",
  "severity": "medium",
  "category": "network",
  "escalated": false,
  "error_count": 0,
  "tool_calls": ["query_vector_db", "fetch_external_api"],
  "history": [...]
}
```

### Check ticket status

```bash
curl http://localhost:8080/api/v1/tickets/TKT-001/status \
  -u user:changeme-in-production
```

## How the Self-Correction Loop Works

When the vector database returns low-confidence results and no ServiceNow incident is found, the agent enters a **self-correction loop**:

```
fetch_external_api → [no incident found] → self_correct
                                               │
                      ┌────────────────────────┘
                      ▼
              attempt 1: runs script with intentional bug
                         (_undefined_diagnostic_function)
                         error captured → error_count = 1
                      │
                      ▼
              attempt 2: generate_corrected_script() strips
                         broken lines, re-runs clean script
                         → if success, loops back to fetch
                      │
                      ▼
              attempt 3+: error_count ≥ 3 → escalate_human
```

The loop demonstrates an agent that can **detect its own failures and apply targeted fixes** before escalating to a human, rather than failing immediately.

## Running Tests

### Python (agent-core)

```bash
cd agent-core
pip install -r requirements.txt pytest pytest-cov
MOCK_LLM=true CHROMA_HOST=localhost CHROMA_PORT=8001 pytest tests/ -v --cov=app
```

### Java (ticket-service)

```bash
cd ticket-service
mvn clean test
```

### Validate Docker Compose

```bash
docker compose config --quiet
```

## CI/CD

GitHub Actions runs three jobs on every push and pull request to `main`:

| Job | What it does |
|-----|-------------|
| `python-test` | Installs deps, runs pytest with `MOCK_LLM=true`, uploads coverage to Codecov |
| `java-build` | Runs `mvn clean test` and verifies the JAR artifact builds |
| `compose-validate` | Runs `docker compose config` to catch YAML/env errors |

## Project Structure

```
enterprise-support-agent/
├── agent-core/
│   ├── app/
│   │   ├── config.py              # pydantic-settings env config
│   │   ├── main.py                # FastAPI app + lifespan KB seeder
│   │   ├── graph/
│   │   │   ├── state.py           # AgentState TypedDict
│   │   │   └── agent_graph.py     # LangGraph StateGraph + routing
│   │   ├── nodes/
│   │   │   └── nodes.py           # 6 node functions
│   │   └── tools/
│   │       ├── vector_search.py   # ChromaDB client + 20-entry KB
│   │       ├── external_api.py    # Mock ServiceNow integration
│   │       └── code_executor.py   # Subprocess sandbox + self-correction
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_graph.py          # 14 tests, full graph integration
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pytest.ini
├── ticket-service/
│   ├── src/main/java/com/enterprise/ticketservice/
│   │   ├── controller/            # TicketController
│   │   ├── service/               # TicketOrchestrationService
│   │   ├── model/                 # Ticket, AgentResponse records
│   │   ├── config/                # WebClientConfig
│   │   ├── security/              # SecurityConfig (HTTP Basic)
│   │   └── exception/             # GlobalExceptionHandler (RFC 9457)
│   ├── src/test/
│   ├── pom.xml
│   └── Dockerfile
├── .github/workflows/ci.yml
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## License

MIT
