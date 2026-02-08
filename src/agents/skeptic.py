# Skeptic/Critic Agent - Quality control and relevance checking
#
# This agent will:
# - Challenge the hype and validate the topic's worthiness
# - Ask critical questions:
#   - "Is this actually new or just repackaged?"
#   - "Is there sufficient evidence to support claims?"
#   - "Is this relevant to our target audience?"
#   - "Are we missing important context or counterarguments?"
#
# - Evaluate research quality:
#   - Source credibility
#   - Citation quality and quantity
#   - Logical consistency
#   - Potential biases
#
# - Make routing decisions:
#   - APPROVE: Topic is worthy, send to Writer
#   - REJECT: Topic is not worthy, send back to Scout with detailed feedback
#   - NEED_MORE_EVIDENCE: Insufficient research, send back to Researcher with specific requests
#
# - Provide detailed feedback for rejected or incomplete topics
# - Maintain high standards to ensure quality content
# - This is the key agent that creates feedback loops in the graph
