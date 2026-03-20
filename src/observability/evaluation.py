"""
LangSmith evaluation integration for AI Newsroom.

Provides:
- Automated LLM-as-judge evaluation of article quality
- Research depth scoring
- LangSmith dataset management for regression testing
- Full evaluation suite runner
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NewsroomEvaluator:
    """
    Runs structured evaluations against completed newsroom workflows.

    Evaluators post their scores back to LangSmith as feedback entries
    associated with the originating run ID, making quality trends
    visible over time in the LangSmith UI.

    All methods gracefully no-op when LangSmith tracing is disabled.
    """

    # Criteria and their LangSmith feedback keys
    ARTICLE_CRITERIA: Dict[str, str] = {
        "clarity":    "Evaluate the article's clarity and readability (0-1). "
                      "Does it explain concepts clearly without jargon overload?",
        "accuracy":   "Evaluate the article's factual accuracy (0-1). "
                      "Are claims specific and well-supported by citations?",
        "engagement": "Evaluate the article's engagement level (0-1). "
                      "Is the writing interesting and likely to retain readers?",
        "structure":  "Evaluate the article's structural quality (0-1). "
                      "Does it have a clear intro, body, and conclusion?",
    }

    RESEARCH_CRITERIA: Dict[str, str] = {
        "source_diversity":  "Evaluate diversity of research sources (0-1). "
                             "Are multiple high-quality sources cited?",
        "credibility":       "Evaluate average source credibility (0-1). "
                             "Are sources from reputable venues (Nature, ArXiv, etc.)?",
        "claim_specificity": "Evaluate claim specificity (0-1). "
                             "Are claims backed by specific data/numbers, not vague assertions?",
    }

    def __init__(self) -> None:
        self._client = None
        self._tracing_enabled = False
        self._llm = None
        self._try_init()

    def _try_init(self) -> None:
        """Attempt to initialise LangSmith client and LLM. Fail silently."""
        try:
            from .tracing import get_langsmith_client, is_tracing_enabled
            self._client = get_langsmith_client()
            self._tracing_enabled = is_tracing_enabled()
        except Exception:
            pass

        if self._tracing_enabled:
            try:
                from src.utils.llm_utils import get_llm_client
                from src.utils.config import get_config
                cfg = get_config()
                self._llm = get_llm_client(
                    provider=cfg.llm.provider,
                    model=cfg.llm.model,
                )
                logger.info("NewsroomEvaluator ready")
            except Exception as exc:
                logger.debug(f"NewsroomEvaluator LLM init failed: {exc}")

    # ------------------------------------------------------------------
    # Article quality evaluation
    # ------------------------------------------------------------------

    async def evaluate_article_quality(
        self,
        run_id: str,
        article_text: str,
        topic: str = "",
    ) -> Dict[str, float]:
        """
        LLM-as-judge: score the final article on clarity, accuracy,
        engagement, and structure.

        Args:
            run_id:       LangSmith run UUID to attach feedback to.
            article_text: The full article markdown text.
            topic:        Optional topic string for context.

        Returns:
            Dict mapping criterion name → score (0-1).
        """
        scores: Dict[str, float] = {}
        if not self._tracing_enabled or not self._llm or not article_text:
            return scores

        for criterion, description in self.ARTICLE_CRITERIA.items():
            score = await self._score_with_llm(
                text=article_text,
                criterion=criterion,
                description=description,
                context=f"Article topic: {topic}",
            )
            scores[criterion] = score
            self._post_feedback(run_id, f"article_{criterion}", score)

        # Composite quality score
        if scores:
            composite = sum(scores.values()) / len(scores)
            scores["composite_quality"] = composite
            self._post_feedback(run_id, "article_composite_quality", composite)

        logger.info(
            f"Article quality scores: "
            + ", ".join(f"{k}={v:.2f}" for k, v in scores.items())
        )
        return scores

    # ------------------------------------------------------------------
    # Research depth evaluation
    # ------------------------------------------------------------------

    async def evaluate_research_depth(
        self,
        run_id: str,
        research_notes: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Score the quality of gathered research notes.

        Args:
            run_id:         LangSmith run UUID.
            research_notes: List of ResearchNote dicts from state.

        Returns:
            Dict mapping criterion → score (0-1).
        """
        scores: Dict[str, float] = {}
        if not self._tracing_enabled or not research_notes:
            return scores

        # Build a text summary of the research for the LLM to evaluate
        research_text = "\n".join(
            f"- [{note.get('citation', 'unknown')}] "
            f"credibility={note.get('credibility_score', 0):.1f}: "
            f"{note.get('claim', '')}"
            for note in research_notes[:20]  # cap at 20 to avoid huge prompts
        )

        for criterion, description in self.RESEARCH_CRITERIA.items():
            score = await self._score_with_llm(
                text=research_text,
                criterion=criterion,
                description=description,
                context=f"Number of sources: {len(research_notes)}",
            )
            scores[criterion] = score
            self._post_feedback(run_id, f"research_{criterion}", score)

        logger.info(
            f"Research depth scores: "
            + ", ".join(f"{k}={v:.2f}" for k, v in scores.items())
        )
        return scores

    # ------------------------------------------------------------------
    # LangSmith dataset management
    # ------------------------------------------------------------------

    def create_evaluation_dataset(
        self,
        name: str,
        examples: List[Dict[str, Any]],
        description: str = "",
    ) -> Optional[str]:
        """
        Create (or update) a LangSmith dataset for regression evaluation.

        Each example should have "inputs" and "outputs" keys::

            examples = [
                {
                    "inputs":  {"topic": "Quantum computing"},
                    "outputs": {"article_quality": 0.85},
                }
            ]

        Args:
            name:        Dataset name shown in LangSmith UI.
            examples:    List of input/output example dicts.
            description: Optional description.

        Returns:
            Dataset ID string, or None on failure.
        """
        if not self._client:
            logger.debug("LangSmith client not available; skipping dataset creation.")
            return None

        try:
            # Create or retrieve dataset
            try:
                dataset = self._client.create_dataset(
                    dataset_name=name,
                    description=description or f"Newsroom.ai evaluation dataset: {name}",
                )
            except Exception:
                # Dataset may already exist — look it up
                datasets = list(self._client.list_datasets(dataset_name=name, limit=1))
                if not datasets:
                    raise
                dataset = datasets[0]

            # Add examples
            for example in examples:
                self._client.create_example(
                    inputs=example.get("inputs", {}),
                    outputs=example.get("outputs", {}),
                    dataset_id=dataset.id,
                )

            logger.info(
                f"LangSmith dataset '{name}' updated "
                f"({len(examples)} examples) | id={dataset.id}"
            )
            return str(dataset.id)

        except Exception as exc:
            logger.warning(f"Failed to create LangSmith dataset '{name}': {exc}")
            return None

    async def run_evaluation_suite(
        self,
        dataset_name: str,
        run_newsroom_fn: Any,  # async callable that returns a NewsroomState
    ) -> Dict[str, Any]:
        """
        Run the full evaluation suite against all examples in a dataset.

        Args:
            dataset_name:    Name of an existing LangSmith dataset.
            run_newsroom_fn: Async callable accepting an example dict and
                             returning the final NewsroomState.

        Returns:
            Summary dict with aggregate scores per criterion.
        """
        if not self._client:
            return {"error": "LangSmith tracing not enabled"}

        try:
            datasets = list(
                self._client.list_datasets(dataset_name=dataset_name, limit=1)
            )
            if not datasets:
                return {"error": f"Dataset '{dataset_name}' not found"}

            dataset = datasets[0]
            examples = list(self._client.list_examples(dataset_id=dataset.id))

            logger.info(
                f"Running evaluation suite against '{dataset_name}' "
                f"({len(examples)} examples)"
            )

            all_scores: Dict[str, List[float]] = {}

            for example in examples:
                try:
                    state = await run_newsroom_fn(example.inputs)
                    run_id = state.get("metadata", {}).get("langsmith_run_id", "")

                    article_scores = await self.evaluate_article_quality(
                        run_id=run_id,
                        article_text=state.get("draft", ""),
                        topic=state.get("topic", ""),
                    )
                    for k, v in article_scores.items():
                        all_scores.setdefault(k, []).append(v)

                except Exception as exc:
                    logger.warning(f"Evaluation failed for example: {exc}")

            # Aggregate
            summary = {
                k: round(sum(v) / len(v), 4)
                for k, v in all_scores.items()
                if v
            }
            logger.info(f"Evaluation suite complete: {summary}")
            return summary

        except Exception as exc:
            logger.error(f"Evaluation suite failed: {exc}")
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _score_with_llm(
        self,
        text: str,
        criterion: str,
        description: str,
        context: str = "",
    ) -> float:
        """
        Ask the LLM to score 'text' on 'criterion' and return a 0-1 float.
        Returns 0.5 (neutral) on any failure.
        """
        if not self._llm:
            return 0.5

        prompt = (
            f"You are an expert content evaluator. "
            f"Score the following text on ONE specific criterion.\n\n"
            f"Criterion: {criterion}\n"
            f"Description: {description}\n"
            f"Context: {context}\n\n"
            f"Text to evaluate:\n{text[:3000]}\n\n"
            f"Respond with ONLY a JSON object: {{\"score\": <float 0.0 to 1.0>, \"reason\": \"<one sentence>\"}}"
        )

        try:
            from langchain_core.messages import HumanMessage
            import json

            response = await self._llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            parsed = json.loads(content)
            score = float(parsed.get("score", 0.5))
            score = max(0.0, min(1.0, score))   # clamp
            return score

        except Exception as exc:
            logger.debug(f"LLM scoring failed for criterion '{criterion}': {exc}")
            return 0.5

    def _post_feedback(
        self, run_id: str, key: str, score: float
    ) -> None:
        """Post a single feedback record to LangSmith."""
        if not self._client or not run_id:
            return
        try:
            self._client.create_feedback(
                run_id=run_id,
                key=key,
                score=score,
            )
        except Exception as exc:
            logger.debug(f"Failed to post feedback '{key}': {exc}")
