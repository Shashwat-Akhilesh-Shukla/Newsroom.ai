# Quick Start Guide - Phase 2

## Prerequisites

- Python 3.10+
- OpenAI API key (or Anthropic)

## Setup (5 minutes)

### 1. Install Dependencies

```bash
cd AI_NEWSROOM
pip install -r requirements.txt
```

### 2. Set API Key

**Option A: Environment Variable**
```bash
export OPENAI_API_KEY='your-key-here'
```

**Option B: .env File**
```bash
# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env
```

### 3. Test the Implementation

```bash
python tests/test_phase2.py
```

## Expected Output

```
============================================================
AI NEWSROOM - Phase 2 Testing
Scout & Researcher Agents
============================================================

✓ Using LLM: openai/gpt-4

Testing API Clients...
  ✓ Fetched 30 topics from Hacker News
  ✓ Fetched 10 papers from ArXiv

Testing Scout Agent...
  Topic: "..."
  Confidence: 0.85
  Next Agent: researcher
✓ Scout agent test passed!

Testing Researcher Agent...
  Research Notes: 12
  Next Agent: skeptic
✓ Researcher agent test passed!

============================================================
✅ All tests passed! Scout → Researcher flow is working.
============================================================
```

## What's Working

✅ Scout discovers trending topics from HackerNews, ArXiv, Google Trends  
✅ Scout analyzes topics using GPT-4 and calculates confidence scores  
✅ Researcher gathers sources and conducts deep research  
✅ Researcher extracts claims and synthesizes findings  
✅ Full Scout → Researcher flow with state management  

## Troubleshooting

### No API Key Error
```
❌ No LLM API key found!
```
**Fix:** Set `OPENAI_API_KEY` environment variable

### Import Errors
```
ModuleNotFoundError: No module named 'langchain'
```
**Fix:** Run `pip install -r requirements.txt`

### Low Confidence Scores
If Scout keeps rescanning, lower the threshold:
```bash
export SCOUT_CONFIDENCE_THRESHOLD=0.5
```

## Next Steps

Phase 2 is complete! Ready for Phase 3:
- Skeptic agent (quality control)
- Writer agent (draft creation)
- Editor agent (review)
- Publisher agent (publishing)
- LangGraph workflow integration

## Documentation

- [Phase 2 Implementation](docs/phase2_implementation.md) - Full documentation
- [Architecture](docs/architecture.md) - System design
- [Project Structure](docs/project_structure.md) - File organization
