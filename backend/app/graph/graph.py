"""
LangGraph Workflow Orchestration for Multi-Agent Research System.

Defines the graph structure, routing logic, and workflow execution.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END

from app.graph.state import AgentState, create_initial_state, finalize_state
from app.graph.routing_logic import classify_tier

logger = logging.getLogger(__name__)


class ResearchWorkflow:
    """Multi-agent research workflow orchestrator."""
    
    def __init__(self):
        """Initialize workflow graph."""
        self.graph = self._build_graph()
        self.compiled_graph = None
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        
        # Create graph
        workflow = StateGraph(AgentState)
        
        # Add nodes (agents)
        workflow.add_node("router", self._router_node)
        workflow.add_node("intake", self._intake_node)
        workflow.add_node("lookup", self._lookup_node)
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("search", self._search_node)
        workflow.add_node("quant", self._quant_node)
        workflow.add_node("source_tier", self._source_tier_node)
        workflow.add_node("writer", self._writer_node)
        workflow.add_node("originality", self._originality_node)
        workflow.add_node("critic", self._critic_node)
        workflow.add_node("finalize", self._finalize_node)
        
        # Set entry point
        workflow.set_entry_point("router")
        
        # Define edges and conditional routing
        
        # Router decides: simple → lookup, complex → intake
        workflow.add_conditional_edges(
            "router",
            self._route_by_tier,
            {
                "simple": "lookup",
                "verify": "intake",  # Verification also goes through full pipeline
                "complex": "intake"
            }
        )
        
        # Lookup → finalize (simple path complete)
        workflow.add_edge("lookup", "finalize")
        
        # Intake → check if clarification needed
        workflow.add_conditional_edges(
            "intake",
            self._check_clarification,
            {
                "clarify": "finalize",  # Need clarification, end workflow
                "continue": "planner"
            }
        )
        
        # Complex path: planner → search → quant → source_tier → writer
        workflow.add_edge("planner", "search")
        workflow.add_edge("search", "quant")
        workflow.add_edge("quant", "source_tier")
        workflow.add_edge("source_tier", "writer")
        
        # Writer → originality check
        workflow.add_edge("writer", "originality")
        
        # Originality → critic (or back to writer if failed)
        workflow.add_conditional_edges(
            "originality",
            self._check_originality,
            {
                "approved": "critic",
                "revise": "writer"
            }
        )
        
        # Critic → finalize or back to writer/search
        workflow.add_conditional_edges(
            "critic",
            self._check_critic_decision,
            {
                "approved": "finalize",
                "revise_writer": "writer",
                "revise_search": "search",  # Major issues, re-search
                "max_revisions": "finalize"  # Hit revision limit
            }
        )
        
        # Finalize → END
        workflow.add_edge("finalize", END)
        
        return workflow
    
    def compile(self):
        """Compile the graph for execution."""
        if not self.compiled_graph:
            self.compiled_graph = self.graph.compile()
        return self.compiled_graph
    
    async def execute(
        self,
        query: str,
        domain: str = "fintech",
        tools: Dict[str, Any] = None,
        user_id: str = None,
        session_id: str = None
    ) -> AgentState:
        """
        Execute the research workflow.
        
        Args:
            query: User query
            domain: Domain (fintech, healthcare, agri)
            tools: Available tools
            user_id: User ID
            session_id: Session ID
            
        Returns:
            Final state
        """
        logger.info(f"Executing workflow for query: {query}")
        
        # Create initial state
        initial_state = create_initial_state(
            query=query,
            domain=domain,
            tools=tools or {},
            user_id=user_id,
            session_id=session_id
        )
        
        # Compile graph if not already compiled
        graph = self.compile()
        
        # Execute workflow
        try:
            final_state = await graph.ainvoke(initial_state)
            logger.info(f"Workflow completed: stage={final_state.get('current_stage')}")
            return final_state
        except Exception as exc:
            logger.error(f"Workflow execution failed: {exc}", exc_info=True)
            # Return error state
            return {
                **initial_state,
                "current_stage": "failed",
                "errors": [f"Workflow failed: {str(exc)}"],
                "final_answer": f"An error occurred while processing your query: {str(exc)}"
            }
    
    # Node implementations
    
    async def _router_node(self, state: AgentState) -> AgentState:
        """Router node - classifies query tier."""
        from app.graph.routing_logic import router_agent
        return router_agent(state)
    
    async def _intake_node(self, state: AgentState) -> AgentState:
        """Intake node - extracts research objective."""
        from app.agents.intake import run
        return await run(state)
    
    async def _lookup_node(self, state: AgentState) -> AgentState:
        """Lookup node - simple query handler."""
        from app.agents.lookup import run_lookup_agent
        return await run_lookup_agent(state)
    
    async def _planner_node(self, state: AgentState) -> AgentState:
        """Planner node - creates research plan."""
        from app.agents.planner import run_planner_agent
        return await run_planner_agent(state)
    
    async def _search_node(self, state: AgentState) -> AgentState:
        """Search node - retrieves information."""
        from app.agents.search import run_search_agent
        return await run_search_agent(state)
    
    async def _quant_node(self, state: AgentState) -> AgentState:
        """Quant node - quantitative analysis."""
        from app.agents.quant import run_quant_agent
        return await run_quant_agent(state)
    
    async def _source_tier_node(self, state: AgentState) -> AgentState:
        """Source tier node - grades sources."""
        from app.agents.source_tier import run_source_tier_agent
        return await run_source_tier_agent(state)
    
    async def _writer_node(self, state: AgentState) -> AgentState:
        """Writer node - generates report."""
        from app.agents.writer import run_writer_agent
        return await run_writer_agent(state)
    
    async def _originality_node(self, state: AgentState) -> AgentState:
        """Originality node - checks plagiarism."""
        from app.agents.orginality import run_originality_agent
        return await run_originality_agent(state)
    
    async def _critic_node(self, state: AgentState) -> AgentState:
        """Critic node - quality control."""
        from app.agents.critic import run_critic_agent
        return await run_critic_agent(state)
    
    async def _finalize_node(self, state: AgentState) -> AgentState:
        """Finalize node - prepares final output."""
        logger.info("Finalizing workflow...")
        
        final_report = None  # Initialize to None
        
        # Extract final answer based on path taken
        if state.get("lookup_executed"):
            # Simple path
            final_answer = state.get("answer", "No answer available")
        elif state.get("draft_report"):
            # Complex path - use report
            draft = state["draft_report"]
            exec_summary = draft.get("executive_summary", "").strip()
            main_body = draft.get("main_content", "Report generation incomplete").strip()
            # Combine executive summary + main body if summary is not already embedded in body
            if exec_summary and exec_summary not in main_body:
                final_answer = f"{exec_summary}\n\n{main_body}"
            else:
                final_answer = main_body
            
            # Create final report structure
            final_report = {
                "title": draft.get("report_title", "Research Report"),
                "executive_summary": draft.get("executive_summary", ""),
                "content": draft.get("main_content", ""),
                "references": draft.get("references", []),
                "metadata": {
                    "word_count": draft.get("word_count", 0),
                    "citations": draft.get("citations_count", 0),
                    "quality_score": state.get("overall_quality_score", 0),
                    "tier_1_2_citations": draft.get("tier_1_2_citations", 0)
                }
            }
        else:
            final_answer = "Unable to complete research query"
        
        # Finalize state
        return finalize_state({
            **state,
            "final_answer": final_answer,
            "final_report": final_report
        })
    
    # Routing logic
    
    def _route_by_tier(self, state: AgentState) -> Literal["simple", "verify", "complex"]:
        """Route based on query tier."""
        tier = state.get("tier", "complex")
        logger.info(f"Routing by tier: {tier}")
        
        if tier == "simple":
            return "simple"
        elif tier == "verify":
            return "verify"
        else:
            return "complex"
    
    def _check_clarification(self, state: AgentState) -> Literal["clarify", "continue"]:
        """Check if query needs clarification."""
        needs_clarification = state.get("needs_clarification", False)
        
        if needs_clarification:
            logger.info("Query needs clarification, ending workflow")
            return "clarify"
        else:
            return "continue"
    
    def _check_originality(self, state: AgentState) -> Literal["approved", "revise"]:
        """Check originality results."""
        originality_check = state.get("originality_check")
        
        if not originality_check:
            # No check performed, proceed
            return "approved"
        
        recommendation = originality_check.get("recommendation", "APPROVED")
        
        if recommendation == "REVISION_REQUIRED":
            revision_count = state.get("revision_count", 0)
            max_revisions = state.get("max_revisions", 2)
            
            if revision_count < max_revisions:
                logger.info(f"Originality revision required (attempt {revision_count + 1}/{max_revisions})")
                state["revision_count"] = revision_count + 1
                return "revise"
            else:
                logger.warning("Max originality revisions reached, proceeding anyway")
                return "approved"
        
        return "approved"
    
    def _check_critic_decision(
        self,
        state: AgentState
    ) -> Literal["approved", "revise_writer", "revise_search", "max_revisions"]:
        """Check critic decision and route accordingly."""
        critic_feedback = state.get("critic_feedback")
        
        if not critic_feedback:
            # No feedback, approve
            return "approved"
        
        decision = critic_feedback.get("decision", "APPROVED")
        revision_count = state.get("revision_count", 0)
        max_revisions = state.get("max_revisions", 2)
        
        # Check revision limit
        if revision_count >= max_revisions:
            logger.warning(f"Max revisions reached ({revision_count}), finalizing anyway")
            return "max_revisions"
        
        if decision == "APPROVED" or decision == "APPROVED_WITH_MINOR_REVISIONS":
            logger.info(f"Critic approved report: {decision}")
            return "approved"
        
        elif decision == "REVISION_REQUIRED":
            # Increment revision count
            state["revision_count"] = revision_count + 1
            
            # Check if issues are fundamental (need re-search) or just writing
            critical_issues = critic_feedback.get("critical_issues", [])
            
            # If evidence quality or completeness issues, re-search
            needs_research = any(
                issue.get("category") in ["evidence_quality", "completeness"]
                for issue in critical_issues
            )
            
            if needs_research:
                logger.info(f"Critical evidence issues, re-searching (revision {revision_count + 1})")
                return "revise_search"
            else:
                logger.info(f"Revising writer (revision {revision_count + 1})")
                return "revise_writer"
        
        elif decision == "REJECTED":
            # Rejection means major issues, re-search
            logger.warning("Report rejected by critic, re-searching")
            state["revision_count"] = revision_count + 1
            return "revise_search"
        
        # Default: approve
        return "approved"


# Global workflow instance
_workflow_instance = None


def get_workflow() -> ResearchWorkflow:
    """Get or create workflow instance."""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = ResearchWorkflow()
    return _workflow_instance


async def execute_research_workflow(
    query: str,
    domain: str = "fintech",
    tools: Dict[str, Any] = None,
    user_id: str = None,
    session_id: str = None
) -> AgentState:
    """
    Execute research workflow.
    
    Args:
        query: User query
        domain: Domain
        tools: Available tools
        user_id: User ID
        session_id: Session ID
        
    Returns:
        Final state
    """
    workflow = get_workflow()
    return await workflow.execute(
        query=query,
        domain=domain,
        tools=tools,
        user_id=user_id,
        session_id=session_id
    )
