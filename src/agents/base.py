# Base agent class for all AI Newsroom agents
#
# This file will define:
# - BaseAgent: Abstract base class for all agents
#   - Common interface for all agents
#   - State reading and writing methods
#   - LLM interaction utilities
#   - Logging and monitoring hooks
#   - Error handling and retry logic
#
# - AgentDecision: Enum or class for agent routing decisions
#   - CONTINUE, REJECT, APPROVE, NEED_MORE_EVIDENCE, etc.
#
# - AgentResponse: Standardized response format
#   - decision: Routing decision
#   - data: Agent-specific output
#   - feedback: Optional feedback for other agents
#   - metadata: Execution metadata (time, tokens used, etc.)
