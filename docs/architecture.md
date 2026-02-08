# AI Newsroom Architecture

## Overview
The AI Newsroom is a multi-agent system built with LangGraph that autonomously creates high-quality content through a collaborative workflow of specialized agents.

## Mental Model: Newsroom, Not Assembly Line
This system is designed like an editorial newsroom with distinct roles, feedback loops, and quality gates - not a linear ETL pipeline.

## Agents

### 1. Trend Scout Agent
**Role**: Hunts for trending topics

**Inputs**:
- Twitter/X trending topics
- Hacker News top stories
- ArXiv recent papers
- Google Trends data

**Outputs**:
- Ranked topics with confidence scores

**Routing Logic**:
- If `confidence >= threshold` → Research Agent
- If `confidence < threshold` → Loop back and rescan
- Can receive feedback from Skeptic to adjust search

### 2. Research Agent
**Role**: Conducts deep research

**Inputs**:
- Topic from Scout
- Specific requests from Editor (for fact-checking)

**Outputs**:
- Structured research notes
- Claims with citations
- Open questions

**Routing Logic**:
- Always → Skeptic Agent
- Does NOT make relevance judgments

### 3. Skeptic/Critic Agent
**Role**: Quality control and relevance checking

**Inputs**:
- Research notes from Researcher

**Outputs**:
- Decision: APPROVE, REJECT, or NEED_MORE_EVIDENCE
- Detailed feedback

**Routing Logic**:
- APPROVE → Writer Agent
- REJECT → Scout Agent (with feedback)
- NEED_MORE_EVIDENCE → Research Agent (with specific requests)

**This agent creates the first major feedback loop.**

### 4. Writer Agent
**Role**: Creates article drafts

**Inputs**:
- Approved research from Skeptic
- Rewrite instructions from Editor

**Outputs**:
- Article draft
- Claim list for verification

**Routing Logic**:
- Always → Editor Agent

### 5. Editor Agent
**Role**: Brutal content review

**Inputs**:
- Draft from Writer
- Previous revision history

**Outputs**:
- Decision: ACCEPT, REWRITE, or FACT_CHECK
- Detailed feedback and instructions

**Routing Logic**:
- ACCEPT → Publisher Agent
- REWRITE → Writer Agent (with instructions)
- FACT_CHECK → Research Agent (with specific claims to verify)

**This agent creates cyclic edges that make chains impossible.**

### 6. Publisher Agent
**Role**: Final gatekeeper and publishing

**Inputs**:
- Approved draft from Editor

**Outputs**:
- Decision: PUBLISH or REJECT
- Publishing metadata

**Routing Logic**:
- If all checks pass → PUBLISH (END)
- If any check fails → Editor Agent (with issues)

## State Management

### NewsroomState
```python
{
    "topic": str,
    "confidence": float,
    "research_notes": List[Dict],
    "critic_feedback": List[str],
    "draft": str,
    "editor_comments": List[str],
    "publish_ready": bool,
    "metadata": Dict
}
```

Every agent:
- Reads the full state
- Mutates only its slice
- Emits a routing decision

## Why LangGraph?

This system requires:
- **Stateful memory** across retries
- **Explicit cycles** for revision loops
- **Branching decisions** based on quality gates
- **Agent-level autonomy** with conflicting incentives
- **Recoverable failures** with retry logic
- **Observable execution** for debugging

LangChain alone becomes spaghetti with:
- Rejections and feedback loops
- Conditional reruns
- Quality gates
- Multiple revision cycles

## Multi-Agent Qualification

This system qualifies as "multi-agent" because:
1. At least one agent can block or reject progress (Skeptic, Editor)
2. At least one loop can run indefinitely until quality improves (Editor ↔ Writer)
3. At least two agents have conflicting incentives (Writer wants to publish, Editor wants perfection)
4. State persists across retries

## Execution Flow Example

```
Scout → Researcher → Skeptic → Writer → Editor → Publisher → END
         ↑           ↓                    ↓
         ←───────────┘                    ↓
         ←────────────────────────────────┘
```

The graph is NOT a DAG (Directed Acyclic Graph) - it has cycles, which is the key feature.
