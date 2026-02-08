# State management for the AI Newsroom multi-agent system
#
# This file will define:
# - NewsroomState: The main state object that persists across all agents
#   - topic: Current topic being researched
#   - confidence: Confidence score from Scout agent
#   - research_notes: List of research findings with citations
#   - critic_feedback: Feedback from Skeptic agent
#   - draft: Article draft from Writer agent
#   - editor_comments: Comments and instructions from Editor agent
#   - publish_ready: Boolean flag indicating if content is ready for publishing
#   - metadata: Additional metadata (timestamps, versions, etc.)
#
# - State update functions for each agent
# - State validation and schema enforcement
# - State persistence utilities (save/load from disk)
