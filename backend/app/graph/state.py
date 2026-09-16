"""
State Management for LangGraph Multi-Agent Workflow.

Defines the shared state structure that flows through all agents.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """
    Shared state for the multi-agent research workflow.
    
    This state is passed between all agents and updated incrementally.
    """
    
    # Input
    raw_query: str  # Original user query
    query_text: str  # Processed query text
    user_id: Optional[str]  # User identifier
    session_id: Optional[str]  # Session identifier
    domain: str  # Domain: fintech, healthcare, agri
    
    # Routing
    tier: str  # Query tier: simple, verify, complex
    needs_clarification: bool  # Whether query needs clarification
    
    # Intake Agent Output
    objective: Dict[str, Any]  # Structured research objective
    
    # Planner Agent Output
    research_plan: Dict[str, Any]  # Research plan with sub-questions
    sub_questions: List[str]  # List of sub-questions
    expected_sources: List[str]  # Expected source types
    
    # Search Agent Output
    search_results: List[Dict[str, Any]]  # Retrieved chunks per sub-question
    total_chunks_retrieved: int  # Total chunks count
    search_errors: bool  # Whether search had errors
    
    # Quant Analysis Agent Output
    quant_analysis: Optional[Dict[str, Any]]  # Quantitative analysis results
    numerical_insights_count: int  # Count of insights
    
    # Source Tier Agent Output
    graded_sources: List[Dict[str, Any]]  # Sources with tier grades
    evidence_summary: Dict[str, Any]  # Evidence quality summary
    
    # Writer Agent Output
    draft_report: Optional[Dict[str, Any]]  # Written report
    report_quality: Dict[str, Any]  # Quality metrics
    
    # Originality Check Agent Output
    originality_check: Optional[Dict[str, Any]]  # Originality check results
    originality_passed: bool  # Whether originality check passed
    
    # Critic Agent Output
    critic_feedback: Optional[Dict[str, Any]]  # Critic evaluation
    needs_revision: bool  # Whether report needs revision
    critic_approved: bool  # Whether critic approved
    overall_quality_score: int  # Overall quality score 0-100
    
    # Lookup Agent Output (simple path)
    lookup_executed: bool  # Whether lookup was executed
    answer: Optional[str]  # Simple answer
    source: Optional[str]  # Data source
    confidence: str  # Confidence level
    
    # Final Output
    final_answer: str  # Final answer/report to user
    final_report: Optional[Dict[str, Any]]  # Final formatted report
    
    # Workflow Control
    current_stage: str  # Current workflow stage
    revision_count: int  # Number of revisions performed
    max_revisions: int  # Maximum allowed revisions
    
    # Tools & Services
    tools: Dict[str, Any]  # Available tools for agents
    
    # Errors & Warnings
    errors: List[str]  # Errors encountered
    warnings: List[str]  # Warnings
    
    # Metadata
    started_at: Optional[str]  # Workflow start time
    completed_at: Optional[str]  # Workflow completion time
    total_duration: Optional[float]  # Total duration in seconds


def create_initial_state(
    query: str,
    domain: str = "fintech",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tools: Optional[Dict[str, Any]] = None
) -> AgentState:
    """
    Create initial state for workflow.
    
    Args:
        query: User query
        domain: Domain (fintech, healthcare, agri)
        user_id: Optional user ID
        session_id: Optional session ID
        tools: Optional tools dictionary
        
    Returns:
        Initial AgentState
    """
    from datetime import datetime
    
    return AgentState(
        raw_query=query,
        query_text=query,
        user_id=user_id,
        session_id=session_id,
        domain=domain,
        
        # Defaults
        tier="unknown",
        needs_clarification=False,
        
        objective={},
        research_plan={},
        sub_questions=[],
        expected_sources=[],
        
        search_results=[],
        total_chunks_retrieved=0,
        search_errors=False,
        
        quant_analysis=None,
        numerical_insights_count=0,
        
        graded_sources=[],
        evidence_summary={},
        
        draft_report=None,
        report_quality={},
        
        originality_check=None,
        originality_passed=False,
        
        critic_feedback=None,
        needs_revision=False,
        critic_approved=False,
        overall_quality_score=0,
        
        lookup_executed=False,
        answer=None,
        source=None,
        confidence="unknown",
        
        final_answer="",
        final_report=None,
        
        current_stage="initialized",
        revision_count=0,
        max_revisions=2,
        
        tools=tools or {},
        
        errors=[],
        warnings=[],
        
        started_at=datetime.now().isoformat(),
        completed_at=None,
        total_duration=None
    )


def update_state(current_state: AgentState, updates: Dict[str, Any]) -> AgentState:
    """
    Update state with new values.
    
    Args:
        current_state: Current state
        updates: Dictionary of updates
        
    Returns:
        Updated state
    """
    # Create new state with updates
    new_state = {**current_state, **updates}
    
    # Preserve list/dict accumulation
    if "errors" in updates and "errors" in current_state:
        new_state["errors"] = current_state.get("errors", []) + updates.get("errors", [])
    
    if "warnings" in updates and "warnings" in current_state:
        new_state["warnings"] = current_state.get("warnings", []) + updates.get("warnings", [])
    
    return AgentState(**new_state)


def finalize_state(state: AgentState) -> AgentState:
    """
    Finalize state with completion metadata.
    
    Args:
        state: Current state
        
    Returns:
        Finalized state
    """
    from datetime import datetime
    
    completed_at = datetime.now().isoformat()
    
    # Calculate duration
    if state.get("started_at"):
        try:
            start = datetime.fromisoformat(state["started_at"])
            end = datetime.fromisoformat(completed_at)
            duration = (end - start).total_seconds()
        except:
            duration = None
    else:
        duration = None
    
    return update_state(state, {
        "completed_at": completed_at,
        "total_duration": duration,
        "current_stage": "completed"
    })
