# Editor Agent - Content refinement and brutal quality control
#
# This agent will:
# - Perform rigorous editorial review of the draft
# - Check for:
#   - Logic holes and inconsistencies
#   - Unsupported claims or hallucinations
#   - Tone and voice consistency
#   - Clarity and readability
#   - Unnecessary fluff or verbosity
#   - Grammar and style issues
#   - Proper citation usage
#
# - Enforce editorial standards:
#   - Adherence to style guide
#   - Target audience appropriateness
#   - Technical accuracy
#   - Narrative flow and structure
#
# - Make routing decisions:
#   - ACCEPT: Draft meets standards, send to Publisher
#   - REWRITE: Draft needs improvement, send back to Writer with detailed instructions
#   - FACT_CHECK: Specific claims need verification, send back to Researcher
#
# - Provide detailed, actionable feedback
# - Track revision history and improvements
# - This agent creates cyclic edges that make chains impossible
