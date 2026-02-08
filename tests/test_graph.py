# Integration tests for LangGraph workflow
#
# This file will test:
# - Complete workflow execution from Scout to Publisher
# - Conditional routing between agents:
#   - Scout -> Researcher (high confidence)
#   - Scout -> Scout (low confidence, rescan)
#   - Skeptic -> Writer (approved)
#   - Skeptic -> Scout (rejected)
#   - Skeptic -> Researcher (needs more evidence)
#   - Editor -> Publisher (accepted)
#   - Editor -> Writer (rewrite)
#   - Editor -> Researcher (fact check)
#   - Publisher -> Editor (failed checks)
#
# - Cyclic execution handling:
#   - Multiple revision loops
#   - Loop detection and prevention
#   - Max iteration limits
#
# - State persistence across agent transitions
# - Error recovery and retry logic
# - Graph visualization and debugging
# - Performance metrics (execution time, agent calls)
