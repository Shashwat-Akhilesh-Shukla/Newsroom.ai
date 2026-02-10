# Phase 2: Scout & Research Agents - Implementation Complete

## Overview

Phase 2 implementation adds the Scout and Researcher agents with full API integrations for discovering and researching trending topics.

## What's Implemented

### ✅ API Clients (`src/utils/api_clients.py`)
- **HackerNewsClient**: Fetches top stories and discussions
- **ArXivClient**: Searches academic papers
- **GoogleTrendsClient**: Analyzes search trends (requires `pytrends`)
- **TwitterClient**: Trending topics (optional, requires paid API)
- **TrendAggregator**: Combines all sources
- Rate limiting and retry logic with exponential backoff

### ✅ Scout Agent (`src/agents/scout.py`)
- Discovers trending topics from multiple sources
- LLM-based topic analysis and confidence scoring
- Topic ranking and deduplication
- Routing logic: proceeds to Researcher if confidence ≥ threshold, else rescans
- Max iteration protection

### ✅ Researcher Agent (`src/agents/researcher.py`)
- Generates research plans using LLM
- Gathers sources from ArXiv and Hacker News
- Extracts claims with citations
- Synthesizes research findings
- Always routes to Skeptic (to be implemented in Phase 3)

### ✅ Configuration (`src/utils/config.py`)
- Environment variable management
- LLM provider configuration
- Agent thresholds and limits
- API key management

### ✅ LLM Utilities (`src/utils/llm_utils.py`)
- LLM client initialization (OpenAI, Anthropic)
- Structured JSON output generation
- Prompt template loading from YAML
- Token counting and cost estimation

### ✅ Prompt Templates (`config/agent_prompts.yaml`)
- Scout prompts: topic analysis, confidence scoring
- Researcher prompts: research planning, claim extraction, synthesis

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file (or set environment variables):

```bash
# Required: LLM API Key
OPENAI_API_KEY=your_openai_api_key_here

# Optional: LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.7

# Optional: Agent Configuration
SCOUT_CONFIDENCE_THRESHOLD=0.7
MAX_SCOUT_ITERATIONS=3
MAX_RESEARCH_SOURCES=10

# Optional: Twitter API (paid)
# TWITTER_API_KEY=your_key
# TWITTER_API_SECRET=your_secret
```

### 3. Run Tests

```bash
# Test Phase 2 implementation
python tests/test_phase2.py

# Or use pytest
pytest tests/test_phase2.py -v
```

## How It Works

### Scout Agent Flow

1. **Fetch Trends**: Aggregates from HackerNews, ArXiv, Google Trends
2. **Aggregate**: Deduplicates and ranks topics
3. **Analyze**: Uses LLM to analyze top 5 topics for relevance, novelty, technical depth
4. **Score**: Calculates confidence score (0-1)
5. **Route**: 
   - If confidence ≥ 0.7 → Researcher
   - If confidence < 0.7 → Rescan (up to 3 iterations)
   - If max iterations → END

### Researcher Agent Flow

1. **Plan**: Generates research plan with search queries
2. **Gather**: Fetches sources from ArXiv and HackerNews
3. **Extract**: Uses LLM to extract claims from each source
4. **Synthesize**: Creates comprehensive research summary
5. **Route**: Always → Skeptic (Phase 3)

## Testing

The `tests/test_phase2.py` script tests:

1. ✅ API clients (HackerNews, ArXiv, Google Trends)
2. ✅ Scout agent independently
3. ✅ Researcher agent independently
4. ✅ Scout → Researcher flow
5. ✅ State transitions

## Example Output

```
Topic: "New Breakthrough in Quantum Computing"
Confidence: 0.85
Keywords: ["quantum", "computing", "breakthrough", "qubits"]
Research Notes: 12
Sources: 8 (5 ArXiv papers, 3 HN discussions)
Next Agent: skeptic
```

## API Rate Limits

- **HackerNews**: 2 requests/second (built-in rate limiting)
- **ArXiv**: 0.5 requests/second (recommended by ArXiv)
- **Google Trends**: No official limit (pytrends handles it)
- **Twitter**: Depends on your API tier (optional)

## Troubleshooting

### No LLM API Key
```
❌ No LLM API key found!
Set OPENAI_API_KEY or ANTHROPIC_API_KEY
```
**Solution**: Set your API key in `.env` or environment

### pytrends Not Installed
```
⚠ Google Trends not available (pytrends not installed)
```
**Solution**: `pip install pytrends` (optional)

### Low Confidence Scores
If Scout keeps rescanning with low confidence:
- Check that API clients are returning data
- Lower `SCOUT_CONFIDENCE_THRESHOLD` in config
- Review LLM analysis in logs

## Next Steps (Phase 3)

- [ ] Implement Skeptic agent (quality control)
- [ ] Implement Writer agent (draft creation)
- [ ] Implement Editor agent (review and revision)
- [ ] Implement Publisher agent (final validation)
- [ ] Create LangGraph workflow connecting all agents

## Files Changed

### New Files
- `src/utils/api_clients.py` - API client implementations
- `src/utils/config.py` - Configuration management
- `src/utils/llm_utils.py` - LLM utilities
- `config/agent_prompts.yaml` - Prompt templates
- `tests/test_phase2.py` - Phase 2 tests

### Modified Files
- `src/agents/scout.py` - Complete implementation
- `src/agents/researcher.py` - Complete implementation
- `requirements.txt` - Added tiktoken dependency

## Architecture

```
Scout Agent
    ↓ (confidence ≥ threshold)
Researcher Agent
    ↓ (always)
Skeptic Agent (Phase 3)
    ↓ (if approved)
Writer Agent (Phase 3)
    ↓
Editor Agent (Phase 3)
    ↓
Publisher Agent (Phase 3)
    ↓
END (published)
```

## Notes

- Scout and Researcher are **fully functional** and can run independently
- LangGraph integration will come in Phase 3
- All agents follow the `BaseAgent` interface
- State management is handled by `NewsroomState`
- Logging is configured per agent for debugging
