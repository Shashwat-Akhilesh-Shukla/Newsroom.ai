# AI Newsroom Setup Guide

## Prerequisites
- Python 3.10 or higher
- pip or poetry for package management
- API keys for required services (see below)

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd AI_NEWSROOM
```

### 2. Create a virtual environment
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys
```

## Required API Keys

### Essential
- **OpenAI API Key**: For LLM interactions (required)
  - Get from: https://platform.openai.com/api-keys

### Optional (for full functionality)
- **Twitter/X API**: For trend monitoring
  - Get from: https://developer.twitter.com/
- **GitHub Token**: For repository research
  - Get from: https://github.com/settings/tokens
- **Medium API**: For publishing
  - Get from: https://medium.com/me/settings

## Configuration

### Agent Configuration
Edit the following in `.env`:
- `SCOUT_CONFIDENCE_THRESHOLD`: Minimum confidence to proceed (default: 0.7)
- `MAX_RESEARCH_SOURCES`: Maximum sources per topic (default: 10)
- `MAX_REVISION_LOOPS`: Maximum editor-writer loops (default: 3)

### LLM Configuration
You can specify different models for each agent:
- `SCOUT_MODEL`: Model for Scout agent (default: gpt-3.5-turbo)
- `RESEARCHER_MODEL`: Model for Researcher (default: gpt-4)
- `WRITER_MODEL`: Model for Writer (default: gpt-4)
- etc.

## Running the Application

### Basic usage
```bash
python -m src.main
```

### With custom configuration
```bash
python -m src.main --config config/custom_config.yaml
```

### Development mode
```bash
DEBUG=True python -m src.main
```

## Testing

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_agents.py
```

## Database Setup

### SQLite (default for development)
No setup required - database file will be created automatically.

### PostgreSQL (for production)
```bash
# Update DATABASE_URL in .env
DATABASE_URL=postgresql://user:password@localhost/newsroom

# Run migrations
alembic upgrade head
```

## Troubleshooting

### Import errors
Make sure you're in the virtual environment and all dependencies are installed.

### API rate limits
Configure rate limiting in `src/utils/api_clients.py` or use caching to reduce API calls.

### LLM token limits
Adjust `MAX_RESEARCH_SOURCES` and other limits in `.env` to reduce token usage.

## Next Steps
- Read `docs/architecture.md` to understand the system design
- Check `config/style_guide.md` for content standards
- Review `config/agent_prompts.yaml` to customize agent behavior
