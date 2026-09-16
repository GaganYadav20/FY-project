"""
Planner Agent - Creates research plan with sub-questions.

Breaks down complex research objectives into structured, actionable sub-questions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.prompts.planner import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ResearchPlan(BaseModel):
    """Structured research plan output."""
    research_goal: str = Field(..., description="Clear statement of research goal")
    sub_questions: List[str] = Field(..., description="2-5 specific sub-questions")
    search_strategy: str = Field(..., description="Strategy to gather information")
    expected_sources: List[str] = Field(..., description="Types of sources needed")
    complexity_level: str = Field("medium", description="Estimated complexity: simple/medium/high")


class PlannerAgent:
    """Planner agent that creates research plans."""
    
    def __init__(self, llm_client):
        """
        Initialize Planner Agent.
        
        Args:
            llm_client: LLM client for generating plans
        """
        self.llm = llm_client
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create research plan from objective.
        
        Args:
            state: Current workflow state containing objective
            
        Returns:
            Updated state with research plan
        """
        logger.info("Planner Agent executing...")
        
        try:
            # Extract objective
            objective = state.get("objective", {})
            raw_query = state.get("raw_query", "")
            
            subject = objective.get("subject", "")
            scope = objective.get("scope", "")
            question_type = objective.get("question_type", "")
            
            # Build planning prompt
            objective_text = f"""
Subject: {subject}
Scope: {scope}
Question Type: {question_type}
Original Query: {raw_query}
"""
            
            # Generate plan
            plan = await self._generate_plan(objective_text, question_type)
            
            logger.info(f"Research plan created with {len(plan.sub_questions)} sub-questions")
            
            return {
                "research_plan": {
                    "research_goal": plan.research_goal,
                    "sub_questions": plan.sub_questions,
                    "search_strategy": plan.search_strategy,
                    "expected_sources": plan.expected_sources,
                    "complexity_level": plan.complexity_level
                },
                "current_stage": "planning_complete",
                "sub_questions": plan.sub_questions,  # For easy access
                "expected_sources": plan.expected_sources
            }
            
        except Exception as exc:
            logger.error(f"Planner Agent failed: {exc}", exc_info=True)
            # Fallback: create basic plan from raw query
            return self._create_fallback_plan(state, str(exc))
    
    async def _generate_plan(self, objective_text: str, question_type: str) -> ResearchPlan:
        """
        Generate research plan using LLM.
        
        Args:
            objective_text: Formatted objective description
            question_type: Type of question (factual, comparison, analysis, etc.)
            
        Returns:
            Structured ResearchPlan
        """
        user_prompt = f"""Create a research plan for the following objective:

{objective_text}

Guidelines:
- Generate 2-5 focused sub-questions (more focused is better)
- Order sub-questions logically
- For comparisons, create parallel questions for each entity
- For analysis, go from foundational data → analysis → synthesis
- Specify exact source types needed (regulatory_filings, market_data, etc.)

Return structured JSON."""

        try:
            response = await self.llm.call(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_schema=ResearchPlan
            )
            
            plan = ResearchPlan(**response)
            
            # Validate and adjust
            if len(plan.sub_questions) > 5:
                logger.warning(f"Plan has {len(plan.sub_questions)} questions, trimming to 5")
                plan.sub_questions = plan.sub_questions[:5]
            
            if len(plan.sub_questions) == 0:
                raise ValueError("Plan generated zero sub-questions")
            
            return plan
            
        except Exception as exc:
            logger.error(f"Plan generation failed: {exc}")
            raise
    
    def _create_fallback_plan(self, state: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create a basic fallback plan when LLM fails."""
        raw_query = state.get("raw_query", "")
        objective = state.get("objective", {})
        subject = objective.get("subject", raw_query)
        
        logger.warning("Creating fallback research plan")
        
        return {
            "research_plan": {
                "research_goal": f"Research: {subject}",
                "sub_questions": [
                    f"What is the current information about {subject}?",
                    f"What are the key facts and data points related to {subject}?"
                ],
                "search_strategy": "General web search and financial data lookup",
                "expected_sources": ["web_search", "financial_data", "news"],
                "complexity_level": "medium"
            },
            "current_stage": "planning_fallback",
            "sub_questions": [
                f"What is the current information about {subject}?",
                f"What are the key facts and data points related to {subject}?"
            ],
            "expected_sources": ["web_search", "financial_data"],
            "errors": [f"Planner failed, using fallback: {error}"]
        }


# Standalone function for graph integration
async def run_planner_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run planner agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict with research plan
    """
    from app.services.llm import get_llm_client
    
    llm_client = get_llm_client()
    agent = PlannerAgent(llm_client=llm_client)
    
    result = await agent.run(state)
    
    # Merge with existing state
    return {**state, **result}
