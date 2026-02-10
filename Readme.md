# 🤖 Newsroom.ai

> **Your AI-Powered Editorial Team That Never Sleeps**

Imagine a newsroom where AI agents work together like a real editorial team—discovering trending topics, researching them deeply, challenging assumptions, writing drafts, and polishing them to perfection. That's Newsroom.ai.

Six specialized AI agents collaborate through feedback loops and quality gates to create high-quality technical articles autonomously. No babysitting required.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.20+-green.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 Why This Exists

**TL;DR:** Most AI content systems are glorified templates. This is different.

We built Newsroom.ai to solve a real problem: creating genuinely good technical content at scale. Not keyword-stuffed SEO garbage. Not generic "10 Tips for..." articles. **Real, researched, insightful content** that people actually want to read.

The secret? **Agents that disagree with each other.**

Just like a real newsroom, our AI agents have different jobs and different incentives:
- The **Scout** wants to find the hottest topics
- The **Skeptic** wants to kill hype and demand evidence
- The **Writer** wants to publish quickly
- The **Editor** demands perfection and will send drafts back for rewrites

This tension creates quality. It's messy. It's inefficient. **It works.**

---

## 🎭 Meet Your AI Editorial Team

| Agent | Personality | Superpower | Can Say "No"? |
|-------|-------------|------------|---------------|
| 🔍 **Scout** | Trend hunter, always online | Discovers what's hot on HN, ArXiv, Twitter | ✅ Loops until confident |
| 📚 **Researcher** | Academic librarian | Deep research with proper citations | ❌ Neutral gatherer |
| 🤔 **Skeptic** | The cynic in the room | Challenges hype: "Is this *actually* new?" | ✅ Can reject outright |
| ✍️ **Writer** | Creative wordsmith | Turns research into compelling narratives | ❌ Follows orders |
| 📝 **Editor** | Perfectionist, brutally honest | Catches logic holes and hallucinations | ✅ Forces rewrites |
| 🚀 **Publisher** | Quality gatekeeper | SEO, formatting, duplicate checks | ✅ Final veto power |

**The magic:** Three agents can block progress. This creates feedback loops that improve quality with each iteration.

---

## 🔄 Why LangGraph? (The Honest Answer)

We tried building this with LangChain. It became spaghetti code in about 2 hours.

**The problem:** LangChain is great for linear workflows. But the moment you add:
- ❌ An editor who rejects drafts and sends them back
- ❌ A skeptic who demands more evidence
- ❌ Quality gates that can fail
- ❌ Loops that run until quality improves

...your code becomes an unmaintainable mess of if-statements and callbacks.

**LangGraph solves this** by treating your workflow as a graph with cycles:
- ✅ **Stateful memory** - Agents remember previous attempts
- ✅ **Explicit cycles** - Editor → Writer → Editor is a feature, not a bug
- ✅ **Branching logic** - Each agent decides where to go next
- ✅ **Observable execution** - You can see exactly what's happening

Think of it like Git vs. a linear file system. Once you need branches and merges, you need Git. Once you need feedback loops and quality gates, you need LangGraph.

---

## 🏗️ How It Actually Works

### The Workflow (Simplified)

```
Scout finds trending topic
    ↓
Researcher gathers evidence
    ↓
Skeptic reviews: "Is this legit?"
    ├─ No → Back to Scout
    └─ Yes → Continue
        ↓
Writer creates draft
    ↓
Editor reviews: "Is this good?"
    ├─ Needs work → Back to Writer
    ├─ Needs facts → Back to Researcher
    └─ Perfect → Continue
        ↓
Publisher validates and publishes
```

**The graph has cycles.** That's the whole point. Quality comes from iteration.

### Real Example

Let's say Scout finds: *"New AI model claims 99% accuracy"*

1. **Scout** (confidence: 0.85): "This is trending on HN and ArXiv!"
2. **Researcher**: Gathers 8 sources, extracts claims with citations
3. **Skeptic**: "Wait, 99% accuracy *on what dataset*? Need more evidence."
4. **Researcher** (again): Digs deeper, finds the actual benchmark details
5. **Skeptic**: "Okay, this checks out. Proceed."
6. **Writer**: Creates draft with proper context and caveats
7. **Editor**: "This paragraph is confusing. Rewrite it."
8. **Writer** (again): Clarifies the confusing section
9. **Editor**: "Good. Ship it."
10. **Publisher**: Checks SEO, formatting, duplicates → Publishes

**Total iterations:** 3 loops. **Time saved vs. human:** ~4 hours. **Quality:** Actually good.

---

## 🚀 Get Started in 5 Minutes

### What You Need
- Python 3.10 or higher
- An OpenAI API key (or Anthropic Claude)
- 5 minutes

### Installation

```bash
# Clone and enter the project
git clone <your-repo-url>
cd AI_NEWSROOM

# Set up Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install everything
pip install -r requirements.txt

# Add your API key
echo "OPENAI_API_KEY=your-key-here" > .env
```

### Test Phase 2 (Scout + Researcher)

```bash
# Run the Phase 2 test
python tests/test_phase2.py
```

You should see:
```
✅ Scout found: "Breakthrough in Quantum Error Correction"
✅ Confidence: 0.85
✅ Researcher gathered 12 sources
✅ All tests passed!
```

**That's it.** Scout and Researcher are working. The other agents are coming in Phase 3.

---

## 📊 Current Status

### ✅ Phase 1: Foundation (Complete)
- Base agent architecture
- State management system
- Project structure

### ✅ Phase 2: Discovery & Research (Complete)
- **Scout Agent** - Finds trending topics from HackerNews, ArXiv, Google Trends
- **Researcher Agent** - Deep research with citations
- **API Integrations** - HN, ArXiv, Google Trends, Twitter (optional)
- **LLM Utilities** - OpenAI/Anthropic integration
- **Tests** - Full Scout → Researcher flow validated

### 🚧 Phase 3: Content Creation (In Progress)
- [ ] Skeptic Agent - Quality control
- [ ] Writer Agent - Draft creation
- [ ] Editor Agent - Review and revision
- [ ] Publisher Agent - Final validation
- [ ] LangGraph Integration - Connect all agents

---

## 🎓 Learn More

### Documentation
- **[Quick Start Guide](docs/QUICKSTART_PHASE2.md)** - Get running in 5 minutes
- **[Phase 2 Walkthrough](docs/phase2_implementation.md)** - Deep dive into Scout & Researcher
- **[Architecture](docs/architecture.md)** - System design philosophy
- **[Project Structure](docs/project_structure.md)** - Where everything lives

### Key Concepts

**Why "Newsroom" and not "Pipeline"?**  
Pipelines are linear. Newsrooms have feedback loops, disagreements, and quality gates. That's what makes content good.

**Why do agents need to disagree?**  
Tension creates quality. If everyone agrees, you get groupthink. If the Editor can force rewrites, the Writer tries harder.

**How is this different from AutoGPT?**  
AutoGPT is one agent with tools. This is six agents with different goals. The architecture is fundamentally different.

---

## 🛠️ Tech Stack

**Core:**
- **LangGraph** - Multi-agent orchestration
- **LangChain** - LLM abstractions
- **OpenAI/Anthropic** - Language models

**Data:**
- **SQLAlchemy** - Database (coming in Phase 3)
- **Redis** - Caching (coming in Phase 3)

**APIs:**
- **Hacker News** - Tech discussions
- **ArXiv** - Academic papers
- **Google Trends** - Search trends
- **Twitter** - Social trends (optional)

---

## 🤝 Contributing

We're building this in public. Contributions welcome!

**Areas we need help:**
- [ ] Additional data sources (Reddit, GitHub trending, etc.)
- [ ] Better prompt engineering for agents
- [ ] Web UI for monitoring agent execution
- [ ] Support for more LLM providers
- [ ] Publishing integrations (Medium, Dev.to, etc.)

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License - Use it, fork it, build on it. Just don't blame us if your AI agents start arguing with each other. (They will. That's the point.)

---

## 💡 The Big Idea

**Most AI content systems are assembly lines.** Input → Process → Output. Fast, efficient, soulless.

**Newsroom.ai is a newsroom.** Messy, iterative, with agents that challenge each other. Slower, more expensive, **way better output.**

We believe the future of AI isn't about making it faster—it's about making it *think* better. And thinking requires disagreement, iteration, and quality gates.

**This is not a chain. This is a graph.**

And graphs are how real work gets done.

---

## 🙏 Acknowledgments

Built with [LangGraph](https://github.com/langchain-ai/langgraph) by LangChain.

Inspired by every editor who ever sent our drafts back with "this needs work" written in red ink. You were right. We hated it. But you were right.

---

**Questions? Issues? Ideas?**  
Open an issue or start a discussion. We're figuring this out together.
