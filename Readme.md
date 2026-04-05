# 🤖 AI Newsroom (Enterprise Multi-Agent Pipeline)

> **Enterprise-grade, Event-driven Multi-Agent System for Autonomous Content Generation**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.20+-green.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Vite-61DAFB.svg)](https://vitejs.dev/)
[![Gemini](https://img.shields.io/badge/LLM-Google%20Gemini-orange.svg)](https://aistudio.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 Executive Summary

AI Newsroom is a sophisticated, fault-tolerant multi-agent system that models an autonomous editorial team. Unlike standard linear LLM wrappers, this architecture leverages **LangGraph** to construct a complex, stateful directed graph where specialized AI agents dynamically collaborate, debate, and self-correct. 

Engineered for production readiness, the platform features a fully **asynchronous event-driven backend** (FastAPI, WebSockets) paired with a **real-time glassmorphic React dashboard** to provide granular observability over agent state transitions, system memory, and automated debugging loops.

The system guarantees high-quality factual output through rigorous quality gates, strict data schema validation, self-healing JSON parsing, and autonomous fallback mechanisms.

---

## ✨ Key Enterprise Engineering Features

### 🧠 Advanced Multi-Agent Orchestration
- **Stateful Cyclic Workflows (LangGraph):** Implemented non-linear, bidirectional agent routing. Agents retain distributed memory and enforce rework loops (e.g., the *Editor* rejecting a *Writer's* draft, or the *Skeptic* demanding deeper citations from the *Researcher*).
- **Dynamic Governance & Telemetry:** Built a dedicated *Manager* agent that constantly evaluates token budgets, API costs, execution time, and cycle counts, autonomously overriding routing to enforce architectural guardrails.
- **Fault-Tolerant Execution:** Engineered resilient pathways including self-healing JSON repair loops, robust `UnboundLocalError` state scoping fallbacks, and rigorous type-checking before transitions to ensure zero silent pipeline failures.

### ⚡ Real-Time Event-Driven Architecture
- **Centralized Event Bus:** Developed an `emit_event` standardized messaging framework that continuously broadcasts granular state transitions, error logs, and multi-agent metrics.
- **WebSocket Streaming:** Engineered a FastAPI interface that maintains bi-directional live WebSockets, streaming real-time terminal logs and system execution states directly to the consumer UI.

### 🎨 Next-Generation Observability Dashboard
- **Glassmorphic Interactive UI:** Designed a premium, Vite-based React frontend featuring a highly tactile, professional aesthetic explicitly optimized for system monitoring.
- **Live Stateful Graph:** Implemented an interactive SVG-based graph visualization where agent nodes literally "glow" to reflect real-time backend execution context.
- **Native Document Rendering:** Built-in Markdown parser with direct `.docx` serialization and export.

### 🏗️ Scalable & Decoupled Infrastructure
- **Fully Asynchronous Stack:** Leveraged `asyncio`, `httpx`, and FastAPI for completely non-blocking I/O across network calls, LLM inference, and database persistence.
- **Optimized Caching & State Management:** Distributed state tracking via **PostgreSQL** + async ORM, coupled with a **Redis-backed API cache** (TTL-based) to dramatically reduce redundant LLM inference costs and rate-limiting issues.
- **Containerized Ecosystem:** Production-ready `Dockerfile` and `docker-compose` setup for one-click cross-environment deployment.

---

## 🎭 The Multi-Agent Finite State Machine

The core intelligence resolves around separation of concerns. Four independent agents have veto power, creating an adversarial system that mimics human editorial rigor.

| Agent Role | System Function | Execution Privilege |
|-------|-------------|---------------|
| 🔍 **Scout** | Trend anomaly detection via real-time data ingestion (Reddit, ArXiv, etc.) | ✅ Loops until confidence threshold met |
| 📚 **Researcher** | Academic extraction & vectorization via semantic queries | ❌ Execution only |
| 🤔 **Skeptic** | Anomaly validation, hypothesis testing, and hallucination boundary control | ✅ Can forcefully reject to Scout |
| ✍️ **Writer** | Context aggregation and narrative transformation | ❌ Execution only |
| 📝 **Editor** | Formal schema review, logical cohesion, and quality control | ✅ Forces cyclical rewrites to Writer |
| 🚀 **Publisher** | Metadata generation, SEO structuring, and API integration | ✅ Final strict validation gate |
| 👑 **Manager** | Governor node; manages SLA, token budgeting, and state overrides | ✅ Can halt and gracefully exit system |

---

## 🚀 Technical Milestones & Hardening

To ensure industrial-grade reliability, the codebase recently underwent significant refactoring:
-   **API Migration & Resilience:** Upgraded legacy scraping endpoints to modern `ddgs` configurations, eliminating deprecation warnings and ensuring stable runtime intelligence aggregation.
-   **Self-Healing Data Handlers:** Solved critical `JSONDecodeError` edge-cases inherent to LLM outputs through a robust retry and string-repair microservice.
-   **Strict State Serialization:** Enforced rigorous state-dictionary validation to resolve asynchronous `KeyError` bugs during the handoff between Editor and Publisher modules.

---

## 🏗️ Getting Started in Dev

### Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- [Google Gemini API key](https://aistudio.google.com/app/apikey)
- Docker (Optional but recommended for PostgreSQL/Redis provisioning)

### Infrastructure Spin-Up (Docker Recommended)
```bash
# Clone & prepare dotfiles
git clone <your-repo-url>
cd AI_NEWSROOM
cp .env.example .env # Ensure you inject your GEMINI_API_KEY

# Provision Backend, PGSQL, and Redis
docker compose up --build
```

### Local Backend Execution (Standalone)
```bash
# Virtual environment setup
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the backend in streaming mode (WebSockets active)
python -m src.main --stream
```

### Starting the Real-Time Dashboard
```bash
cd frontend
npm install
npm run dev
```

---

## 📁 System Architecture tree

```text
AI_NEWSROOM/
├── src/
│   ├── api/
│   │   └── server.py        # FastAPI application, WebSocket Router, REST mappings
│   ├── agents/
│   │   ├── base.py          # Abstract BaseAgent featuring standardized error bounds
│   │   └── ...              # [Scout, Researcher, Skeptic, Writer, Editor, Publisher, Manager]
│   ├── storage/
│   │   ├── database.py      # SQLAlchemy asyncpg ORM implementation
│   │   └── cache.py         # Distributed Redis caching protocol
│   ├── utils/
│   │   ├── config.py        # Strongly typed Pydantic Configuration
│   │   ├── llm_utils.py     # Gemini Tokenizer, Parsing strategies
│   │   ├── api_clients.py   # Async HTTPX wrappers for external APIs
│   │   └── logging_config.py# Centralized, streamable event-logger
│   ├── graph.py             # DAG declaration and edge-routing algorithms
│   └── state.py             # TypedDict state schema and memory initialization
├── frontend/                # Vite/React SPA ecosystem
│   ├── src/
│   │   ├── components/      # UI: Glassmorphic cards, Terminal View, Graph nodes
│   │   └── hooks/           # useWebSockets hook for real-time reactivity
├── tests/                   # Pytest automated testing suite
├── docker-compose.yml       # Orchestration file
└── Dockerfile               # Efficient, multi-stage build container
```

---

## 🤝 Contributing & Vision

AI Newsroom is an ongoing exploration into the shift from **linear LLM chains** to **autonomous graph-based agency**. 

We are constantly optimizing:
- Semantic evaluation harnesses for automated QA tests.
- Expanding parallelization of Researcher nodes.
- Enhancing WebSocket performance and graph observability.

## 📄 License
MIT License.
