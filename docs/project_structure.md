# AI Newsroom - Project Structure

```
AI_NEWSROOM/
│
├── src/                          # Main source code directory
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # Main entry point and CLI
│   ├── state.py                 # NewsroomState definition and management
│   ├── graph.py                 # LangGraph workflow definition
│   │
│   ├── agents/                  # All agent implementations
│   │   ├── __init__.py
│   │   ├── base.py             # BaseAgent class and common interfaces
│   │   ├── scout.py            # Trend Scout agent
│   │   ├── researcher.py       # Research agent
│   │   ├── skeptic.py          # Skeptic/Critic agent
│   │   ├── writer.py           # Writer agent
│   │   ├── editor.py           # Editor agent
│   │   └── publisher.py        # Publisher agent
│   │
│   ├── utils/                   # Shared utilities
│   │   ├── __init__.py
│   │   ├── api_clients.py      # External API clients (Twitter, ArXiv, etc.)
│   │   ├── llm_utils.py        # LLM interaction utilities and prompts
│   │   ├── logging_config.py   # Logging configuration
│   │   ├── data_processing.py  # Text processing and formatting
│   │   └── config.py           # Configuration management
│   │
│   └── storage/                 # Data persistence
│       ├── __init__.py
│       ├── database.py         # Database layer (SQLite/PostgreSQL)
│       └── cache.py            # Caching layer (in-memory/Redis)
│
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── test_agents.py          # Agent unit tests
│   ├── test_graph.py           # Graph integration tests
│   └── test_utils.py           # Utility function tests
│
├── config/                      # Configuration files
│   ├── agent_prompts.yaml      # LLM prompts for each agent
│   └── style_guide.md          # Content style guide
│
├── docs/                        # Documentation
│   ├── architecture.md         # System architecture overview
│   └── setup.md                # Setup and installation guide
│
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Project configuration
└── Readme.md                    # Project overview (existing)
```

## File Descriptions

### Core Files
- **src/main.py**: Entry point that initializes the LangGraph workflow and runs the newsroom pipeline
- **src/state.py**: Defines the NewsroomState object that persists across all agents
- **src/graph.py**: LangGraph workflow with conditional routing and cyclic edges

### Agents (src/agents/)
Each agent file contains:
- Agent class implementation
- LLM interaction logic
- Routing decision logic
- State reading/writing methods

1. **scout.py**: Monitors Twitter, Hacker News, ArXiv, Google Trends for trending topics
2. **researcher.py**: Conducts deep research and gathers citations
3. **skeptic.py**: Quality control - can APPROVE, REJECT, or request MORE_EVIDENCE
4. **writer.py**: Creates article drafts based on approved research
5. **editor.py**: Brutal review - can ACCEPT, REWRITE, or FACT_CHECK
6. **publisher.py**: Final validation and publishing

### Utilities (src/utils/)
- **api_clients.py**: Clients for Twitter, ArXiv, GitHub, Medium, etc.
- **llm_utils.py**: LLM initialization, prompt templates, token tracking
- **data_processing.py**: Text cleaning, citation formatting, content formatting
- **config.py**: Configuration loading and validation

### Storage (src/storage/)
- **database.py**: Persistent storage for topics, research, drafts, publications
- **cache.py**: In-memory/Redis caching for API responses and LLM outputs

### Configuration (config/)
- **agent_prompts.yaml**: System and user prompts for each agent
- **style_guide.md**: Editorial standards and writing guidelines

### Documentation (docs/)
- **architecture.md**: Detailed system architecture and agent workflow
- **setup.md**: Installation and setup instructions

## Key Features

### Multi-Agent System
- 6 specialized agents with distinct roles
- Feedback loops between agents (not a linear chain)
- Quality gates that can reject and loop back

### LangGraph Integration
- Conditional routing based on agent decisions
- Cyclic execution for revision loops
- Stateful memory across agent interactions
- Observable execution graph

### Extensibility
- Modular agent design
- Configurable prompts and parameters
- Support for multiple LLM providers
- Pluggable storage backends

## Next Steps
1. Set up environment variables in `.env`
2. Install dependencies: `pip install -r requirements.txt`
3. Implement agent logic in each agent file
4. Test individual agents
5. Test complete workflow
6. Deploy and monitor
