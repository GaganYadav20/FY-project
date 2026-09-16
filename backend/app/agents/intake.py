"""
Intake Agent — extracts a structured research objective from a raw query.

Sets needs_clarification=True if the query is too vague to research.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from app.services.llm import LLMError, get_llm_client
from app.graph.state import AgentState
from app.prompts.intake import INTAKE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class IntakeResponse(BaseModel):
    subject: str = ""
    ticker: str = ""
    scope: str = ""
    question_type: str = ""
    needs_clarification: bool = False


async def run(state: AgentState) -> dict:
    """Extract a structured research objective from the raw query."""
    raw_query: str = state.get("raw_query", "")

    try:
        llm = get_llm_client()
        result = await llm.call(
            system_prompt=INTAKE_SYSTEM_PROMPT,
            user_prompt=f"User query: \"{raw_query}\"",
            response_schema=IntakeResponse,
        )

        needs_clarification = result.get("needs_clarification", False)
        subject = result.get("subject", "")

        if not subject or subject.lower() in ("", "unknown", "n/a"):
            needs_clarification = True

        objective = {
            "subject": subject,
            "ticker": result.get("ticker", ""),
            "scope": result.get("scope", ""),
            "question_type": result.get("question_type", ""),
        }

        logger.info("Intake: subject=%s, ticker=%s, clarification=%s",
                     subject, objective["ticker"], needs_clarification)

        return {
            "objective": objective,
            "needs_clarification": needs_clarification,
            "current_stage": "intake",
        }

    except (LLMError, Exception) as exc:
        logger.warning("Intake agent failed: %s", exc)
        # Degrade: use raw query as the objective
        return {
            "objective": {
                "subject": raw_query,
                "ticker": "",
                "scope": "general analysis",
                "question_type": "analysis",
            },
            "needs_clarification": False,
            "current_stage": "intake",
            "errors": [f"Intake: extraction failed, using raw query — {exc}"],
        }
