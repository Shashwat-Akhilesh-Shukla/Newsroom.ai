# 🤖 AI Newsroom

> **A Multi-Agent Content Creation System Built with LangGraph**

AI Newsroom is an autonomous content creation system that mimics a real editorial newsroom. Six specialized AI agents collaborate through feedback loops and quality gates to research, write, and publish high-quality technical articles—no human intervention required.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.20+-green.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 Mental Model: Newsroom, Not Assembly Line

**Think editorial newsroom, not ETL pipeline.**

This isn't a linear chain of LLM calls. It's a collaborative system where agents have **conflicting incentives**, **quality gates**, and **feedback loops**—just like a real newsroom.

### The Agents

| Agent | Role | Can Block Progress? |
|-------|------|---------------------|
| 🔍 **Scout** | Hunts trending topics from Twitter, HN, ArXiv | ✅ (loops until confidence threshold met) |
| 📚 **Researcher** | Deep research with citations | ❌ (neutral gatherer) |
| 🤔 **Skeptic** | Challenges hype and relevance | ✅ (can REJECT or demand MORE_EVIDENCE) |
| ✍️ **Writer** | Drafts articles | ❌ (executes on approved research) |
| 📝 **Editor** | Brutal quality control | ✅ (can force REWRITE or FACT_CHECK) |
| 🚀 **Publisher** | Final validation & publishing | ✅ (SEO, formatting, duplicate checks) |

---

## 🔄 Why LangGraph? Why Not LangChain?

**LangChain becomes spaghetti the moment you add:**
- ❌ Rejections and feedback loops
- ❌ Conditional reruns based on quality
- ❌ Multiple quality gates
- ❌ Cyclic execution paths

**LangGraph gives you:**
- ✅ **Stateful memory** across retries
- ✅ **Explicit cycles** for revision loops
- ✅ **Branching decisions** based on agent outputs
- ✅ **Agent-level autonomy** with conflicting goals
- ✅ **Recoverable failures** with retry logic
- ✅ **Observable execution graph** for debugging

---

## 🏗️ Architecture Overview

### The Execution Graph (Not a DAG!)

<img width="918" height="776" alt="image" src="https://github.com/user-attachments/assets/2200ba4a-34cc-4323-a102-b9df0dcd5bfe" />
<img width="918" height="694" alt="image" src="https://github.com/user-attachments/assets/bc468372-1860-4442-8247-1afd23c8a2dd" />


**Key Insight:** The graph has **cycles**, not a linear flow. This is what makes it a true multi-agent system.

---

## 📊 State Management

Every agent reads and mutates a shared state object:

```python
NewsroomState = {
    "topic": str,                    # Current topic being researched
    "confidence": float,             # Scout's confidence score
    "research_notes": List[Dict],    # Research findings with citations
    "critic_feedback": List[str],    # Skeptic's feedback
    "draft": str,                    # Article draft
    "editor_comments": List[str],    # Editor's instructions
    "publish_ready": bool,           # Ready for publishing?
    "metadata": Dict                 # Timestamps, versions, etc.
}
```

**Each agent:**
1. Reads the full state
2. Mutates only its slice
3. Emits a routing decision

This is **LangGraph thinking**, not chain thinking.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API key (or other LLM provider)
- Optional: Twitter, GitHub, Medium API keys for full functionality

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd AI_NEWSROOM

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

### Configuration

Edit `.env` with your API keys and preferences:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional (for full functionality)
TWITTER_API_KEY=your_twitter_api_key_here
GITHUB_TOKEN=your_github_token_here
MEDIUM_API_KEY=your_medium_api_key_here

# Agent Configuration
SCOUT_CONFIDENCE_THRESHOLD=0.7
MAX_RESEARCH_SOURCES=10
MAX_REVISION_LOOPS=3
```

### Run the Newsroom

```bash
# Start the newsroom pipeline
python -m src.main

# With custom configuration
python -m src.main --config config/custom_config.yaml

# Development mode with verbose logging
DEBUG=True python -m src.main
```

---

## 📁 Project Structure

```
AI_NEWSROOM/
├── src/
│   ├── agents/          # 6 specialized agents + base class
│   │   ├── scout.py
│   │   ├── researcher.py
│   │   ├── skeptic.py
│   │   ├── writer.py
│   │   ├── editor.py
│   │   └── publisher.py
│   ├── utils/           # API clients, LLM utils, data processing
│   ├── storage/         # Database and caching layers
│   ├── main.py          # Entry point
│   ├── graph.py         # LangGraph workflow definition
│   └── state.py         # State management
├── tests/               # Comprehensive test suite
├── config/              # Agent prompts and style guide
├── docs/                # Architecture and setup documentation
└── requirements.txt     # Dependencies
```

See [`docs/project_structure.md`](docs/project_structure.md) for detailed structure.

---

## 🎓 How It Works

### 1. **Scout Agent** - Trend Discovery
- Monitors Twitter, Hacker News, ArXiv, Google Trends
- Ranks topics by novelty, relevance, and engagement
- Calculates confidence scores
- **Decision:** Proceed if confidence ≥ threshold, else rescan

### 2. **Researcher Agent** - Deep Investigation
- Gathers information from papers, blogs, GitHub
- Extracts claims with citations
- Structures research notes
- **Does NOT judge relevance** (that's Skeptic's job)

### 3. **Skeptic Agent** - Quality Control ⚠️
- Challenges hype: "Is this actually new?"
- Validates evidence quality
- **Can APPROVE, REJECT, or demand NEED_MORE_EVIDENCE**
- Creates the first major feedback loop

### 4. **Writer Agent** - Content Creation
- Drafts articles based on approved research
- Maintains consistent tone and style
- Creates claim list for verification
- **Cannot publish** (needs Editor approval)

### 5. **Editor Agent** - Brutal Review ⚠️
- Checks for logic holes and hallucinations
- Enforces editorial standards
- **Can ACCEPT, force REWRITE, or request FACT_CHECK**
- Creates cyclic edges (chains die here, graphs thrive)

### 6. **Publisher Agent** - Final Gatekeeper ⚠️
- SEO optimization and formatting
- Duplicate content detection
- Platform-specific validation
- **Publishes only if all checks pass**

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test suite
pytest tests/test_agents.py
pytest tests/test_graph.py
```

---

## 🎯 What Makes This "Multi-Agent"?

This system qualifies as a **true multi-agent system** because:

1. ✅ **At least one agent can block or reject progress**  
   → Skeptic, Editor, and Publisher all have veto power

2. ✅ **At least one loop can run indefinitely until quality improves**  
   → Editor ↔ Writer revision loop

3. ✅ **At least two agents have conflicting incentives**  
   → Writer wants to publish quickly, Editor demands perfection

4. ✅ **State persists across retries**  
   → NewsroomState maintains context through all feedback loops

**If you don't have these properties, you don't have a multi-agent system—you have a chain.**

---

## 📚 Documentation

- **[Architecture Overview](docs/architecture.md)** - Detailed system design
- **[Setup Guide](docs/setup.md)** - Installation and configuration
- **[Project Structure](docs/project_structure.md)** - File organization
- **[Style Guide](config/style_guide.md)** - Content standards

---

## 🛠️ Technology Stack

- **LangGraph** - Multi-agent orchestration with cyclic graphs
- **LangChain** - LLM abstractions and utilities
- **OpenAI/Anthropic** - LLM providers
- **SQLAlchemy** - Database ORM
- **Redis** - Caching layer
- **Pytest** - Testing framework

---

## 🔮 Roadmap

- [ ] Implement all agent logic
- [ ] Add support for multiple LLM providers
- [ ] Build web UI for monitoring agent execution
- [ ] Add support for image generation and embedding
- [ ] Implement A/B testing for different agent prompts
- [ ] Add analytics dashboard for published content
- [ ] Support for multiple publishing platforms

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph) by LangChain
- Inspired by real editorial newsroom workflows
- Designed to showcase the power of multi-agent systems over simple chains

---

## 💡 Key Takeaway

**This is not a chain. This is a graph.**

The moment you add quality gates, rejections, and feedback loops, you need LangGraph. LangChain alone will become unmaintainable spaghetti.

**Think newsroom, not assembly line.**
