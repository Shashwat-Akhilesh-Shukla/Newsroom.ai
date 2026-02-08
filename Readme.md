Mental model: Newsroom, not assembly line

Think editorial newsroom, not ETL.

Roles:

Scout: hunts trends

Researcher: digs papers

Skeptic: challenges relevance

Writer: drafts

Editor: tears it apart

Publisher: ships only if quality passes

Now we’re talking.

Visualising a REAL LangGraph multi-agent system
High-level graph view
Concrete LangGraph topology (this is the key part)
1. Trend Scout Agent

Inputs:

Twitter, Hacker News, ArXiv, Google Trends
Outputs:

Ranked topics + confidence scores

Decision:

If topic confidence < threshold → loop & rescan

Else → dispatch to Research Agent

This is already conditional routing, not a chain.

2. Research Agent

Reads:

Papers

Blog posts

GitHub READMEs

Produces:

Structured notes

Claims + citations

Open questions

Does NOT decide relevance.

Hands off to Skeptic.

3. Skeptic / Critic Agent (this is what kills chain-ness)

Responsibilities:

Challenge hype

Ask: “Is this actually new?”

Reject shallow topics

Demand more sources

Outcomes:

APPROVE → Writer

REJECT → back to Trend Scout with feedback

NEED_MORE_EVIDENCE → back to Research Agent

This feedback loop is why LangGraph exists.

4. Writer Agent

Writes article draft based on:

Research notes

Skeptic constraints

Target audience persona

But cannot publish.

Output:

Draft v1

Claim list

5. Editor Agent

Brutal role:

Checks logic holes

Enforces tone

Cuts fluff

Flags hallucinations

Decisions:

ACCEPT → Publisher

REWRITE → Writer (with instructions)

FACT_CHECK → Research Agent

This creates cyclic edges. Chains die here. Graphs thrive.

6. Publisher Agent

Final gatekeeper:

SEO check

Medium formatting

Duplicate detection

Scheduling

If any check fails → back to Editor.

What LangGraph adds that LangChain cannot

Be honest with yourself here.

LangGraph gives you:

Stateful memory across retries

Explicit cycles

Branching decisions

Agent-level autonomy

Recoverable failures

Observable execution graph

LangChain alone becomes spaghetti the moment you add:

Rejections

Conditional reruns

Quality gates

Minimal state object (example)
State = {
    "topic": None,
    "confidence": 0.0,
    "research_notes": [],
    "critic_feedback": [],
    "draft": None,
    "editor_comments": [],
    "publish_ready": False
}


Every agent:

Reads state

Mutates only its slice

Emits a decision edge

That is LangGraph thinking.

When this officially qualifies as “multi-agent”

This system earns the title only if:

At least one agent can block or reject progress

At least one loop can run indefinitely until quality improves

At least two agents have conflicting incentives

State persists across retries