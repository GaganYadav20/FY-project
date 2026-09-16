"""
Writer Agent - Drafts structured research reports with citations.

Synthesizes research findings into well-structured, properly cited reports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.prompts.writer import WRITER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class Reference(BaseModel):
    """Single reference entry."""
    id: int = Field(..., description="Reference number")
    source_name: str = Field(..., description="Source name")
    tier: int = Field(..., description="Evidence tier 1-7")
    url: str = Field("", description="URL or identifier")
    access_date: str = Field("", description="Date accessed")


class WriterOutput(BaseModel):
    """Structured writer agent output."""
    report_title: str = Field(..., description="Report title")
    executive_summary: str = Field(..., description="2-3 sentence summary")
    main_content: str = Field(..., description="Full report content with citations")
    references: List[Reference] = Field(default_factory=list, description="Reference list")
    word_count: int = Field(0, description="Approximate word count")
    sections_written: List[str] = Field(default_factory=list, description="Section names")
    citations_count: int = Field(0, description="Total citations")
    tier_1_2_citations: int = Field(0, description="High-quality source citations")
    revision_notes: str = Field("", description="Notes on revisions made")


class WriterAgent:
    """Writer agent for report generation."""
    
    def __init__(self, llm_client):
        """Initialize Writer Agent."""
        self.llm = llm_client
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate research report from all gathered information.
        
        Args:
            state: Workflow state with all research data
            
        Returns:
            Updated state with written report
        """
        logger.info("Writer Agent executing...")
        
        try:
            # Extract all necessary inputs
            research_plan = state.get("research_plan", {})
            search_results = state.get("search_results", [])
            graded_sources = state.get("graded_sources", [])
            quant_analysis = state.get("quant_analysis")
            objective = state.get("objective", {})
            
            # Check if this is a revision
            is_revision = "draft_report" in state
            previous_draft = state.get("draft_report")
            critic_feedback = state.get("critic_feedback")
            
            # Generate report
            if is_revision and previous_draft:
                logger.info("Generating revised report based on critic feedback")
                report = await self._revise_report(
                    previous_draft=previous_draft,
                    feedback=critic_feedback,
                    search_results=search_results,
                    graded_sources=graded_sources,
                    quant_analysis=quant_analysis
                )
            else:
                logger.info("Generating initial report")
                report = await self._generate_initial_report(
                    research_plan=research_plan,
                    search_results=search_results,
                    graded_sources=graded_sources,
                    quant_analysis=quant_analysis,
                    objective=objective
                )
            
            logger.info(f"Report generated: {report.word_count} words, "
                       f"{report.citations_count} citations, "
                       f"{report.tier_1_2_citations} Tier 1-2 citations")
            
            return {
                "draft_report": report.dict(),
                "current_stage": "writing_complete",
                "report_quality": {
                    "word_count": report.word_count,
                    "citations": report.citations_count,
                    "high_tier_citations": report.tier_1_2_citations
                }
            }
            
        except Exception as exc:
            logger.error(f"Writer Agent failed: {exc}", exc_info=True)
            return {
                "draft_report": None,
                "current_stage": "writing_failed",
                "errors": [f"Report writing failed: {str(exc)}"]
            }
    
    async def _generate_initial_report(
        self,
        research_plan: Dict[str, Any],
        search_results: List[Dict],
        graded_sources: List[Dict],
        quant_analysis: Optional[Dict],
        objective: Dict[str, Any]
    ) -> WriterOutput:
        """Generate initial report draft."""
        
        # Build context for LLM
        context = self._build_writing_context(
            research_plan=research_plan,
            search_results=search_results,
            graded_sources=graded_sources,
            quant_analysis=quant_analysis,
            objective=objective
        )
        
        user_prompt = f"""Write a comprehensive, well-structured research report based on the following information:

{context}

Requirements:
1. Synthesize information from multiple sources (don't copy verbatim)
2. Cite every factual claim with [Source Name, Tier X] format
3. Prioritize Tier 1-2 sources in the narrative
4. Include quantitative findings with proper context
5. Structure clearly using Markdown headings:
   ### Executive Summary
   ### Key Policy Settings / Core Metrics (use tables or bullet lists with all relevant numbers)
   ### Economic Outlook & Rationale (inflation forecasts, GDP projections, drivers)
   ### Practical Implications (impact on borrowers, savers, businesses, markets)
   ### Caveats & Limitations
   ### References
6. Be thorough and detailed — at minimum 400 words
7. Professional, authoritative, analytical tone

Return the full report as a Markdown document."""

        try:
            full_prompt = f"{WRITER_SYSTEM_PROMPT}\n\n{user_prompt}"
            response_raw = await self.llm.ainvoke(full_prompt)
            response_text = response_raw.content if hasattr(response_raw, 'content') else str(response_raw)
            response_text = response_text.strip()

            # Try JSON parse; if it fails, treat the whole text as main_content
            import json, re
            if response_text.startswith("{"):
                try:
                    parsed = json.loads(response_text)
                    report = WriterOutput(
                        report_title=parsed.get("report_title", objective.get("subject", "Research Report")),
                        executive_summary=parsed.get("executive_summary", ""),
                        main_content=parsed.get("main_content", response_text),
                        word_count=parsed.get("word_count", 0),
                        sections_written=parsed.get("sections_written", []),
                        citations_count=parsed.get("citations_count", 0),
                        tier_1_2_citations=parsed.get("tier_1_2_citations", 0),
                        revision_notes=parsed.get("revision_notes", "")
                    )
                except (json.JSONDecodeError, KeyError):
                    report = WriterOutput(
                        report_title=objective.get("subject", "Research Report"),
                        executive_summary="",
                        main_content=response_text
                    )
            else:
                # Plain Markdown response — use it directly as the report content
                report = WriterOutput(
                    report_title=objective.get("subject", "Research Report"),
                    executive_summary="",
                    main_content=response_text
                )

            return self._post_process_report(report, graded_sources)

        except Exception as exc:
            logger.error(f"Report generation failed: {exc}")
            raise
    
    async def _revise_report(
        self,
        previous_draft: Dict[str, Any],
        feedback: Optional[Dict[str, Any]],
        search_results: List[Dict],
        graded_sources: List[Dict],
        quant_analysis: Optional[Dict]
    ) -> WriterOutput:
        """Revise report based on critic feedback."""
        
        if not feedback:
            logger.warning("No feedback provided for revision, returning previous draft")
            return WriterOutput(**previous_draft)
        
        # Extract specific issues to address
        critical_issues = feedback.get("critical_issues", [])
        medium_issues = feedback.get("medium_issues", [])
        revision_instructions = feedback.get("revision_instructions", [])
        
        # Build revision context
        context = f"""Previous Report:
Title: {previous_draft.get('report_title', '')}
Content: {previous_draft.get('main_content', '')}

Critic Feedback:
Critical Issues: {critical_issues}
Medium Issues: {medium_issues}
Specific Instructions: {revision_instructions}

Available Sources:
{self._format_sources_for_revision(graded_sources)}

Quantitative Data:
{self._format_quant_for_revision(quant_analysis)}
"""

        user_prompt = f"""{context}

Revise the report to address all feedback:
1. Fix all critical issues (uncited claims, missing sources, etc.)
2. Address medium issues (upgrade citations, improve sections)
3. Follow specific revision instructions
4. Maintain original structure and quality
5. Track what you changed in revision_notes

Return the revised report as a Markdown document."""

        try:
            full_prompt = f"{WRITER_SYSTEM_PROMPT}\n\n{user_prompt}"
            response_raw = await self.llm.ainvoke(full_prompt)
            response_text = response_raw.content if hasattr(response_raw, 'content') else str(response_raw)
            response_text = response_text.strip()

            import json
            if response_text.startswith("{"):
                try:
                    parsed = json.loads(response_text)
                    revised_report = WriterOutput(
                        report_title=parsed.get("report_title", previous_draft.get("report_title", "Research Report")),
                        executive_summary=parsed.get("executive_summary", ""),
                        main_content=parsed.get("main_content", response_text),
                        word_count=parsed.get("word_count", 0),
                        sections_written=parsed.get("sections_written", []),
                        citations_count=parsed.get("citations_count", 0),
                        tier_1_2_citations=parsed.get("tier_1_2_citations", 0),
                        revision_notes=parsed.get("revision_notes", "Addressed critic feedback")
                    )
                except (json.JSONDecodeError, KeyError):
                    revised_report = WriterOutput(
                        report_title=previous_draft.get("report_title", "Research Report"),
                        executive_summary=previous_draft.get("executive_summary", ""),
                        main_content=response_text,
                        revision_notes="Addressed critic feedback"
                    )
            else:
                revised_report = WriterOutput(
                    report_title=previous_draft.get("report_title", "Research Report"),
                    executive_summary=previous_draft.get("executive_summary", ""),
                    main_content=response_text,
                    revision_notes="Addressed critic feedback"
                )

            return revised_report

        except Exception as exc:
            logger.error(f"Report revision failed: {exc}")
            return WriterOutput(**previous_draft)
    
    def _build_writing_context(
        self,
        research_plan: Dict[str, Any],
        search_results: List[Dict],
        graded_sources: List[Dict],
        quant_analysis: Optional[Dict],
        objective: Dict[str, Any]
    ) -> str:
        """Build context string for report writing."""
        
        parts = []
        
        # Research objective
        parts.append(f"Research Objective:")
        parts.append(f"Subject: {objective.get('subject', 'N/A')}")
        parts.append(f"Scope: {objective.get('scope', 'N/A')}")
        parts.append(f"Question Type: {objective.get('question_type', 'N/A')}")
        parts.append("")
        
        # Research plan
        parts.append(f"Research Goal: {research_plan.get('research_goal', 'N/A')}")
        parts.append("")
        
        # Search results by sub-question
        parts.append("Search Results:")
        for idx, result in enumerate(search_results):
            parts.append(f"\nSub-question {idx+1}: {result.get('sub_question', '')}")
            
            chunks = result.get("retrieved_chunks", [])
            for chunk_idx, chunk in enumerate(chunks[:5]):  # Limit chunks to avoid token overflow
                parts.append(f"  Chunk {chunk_idx+1}:")
                parts.append(f"    Content: {chunk.get('content', '')[:200]}...")
                parts.append(f"    Source: {chunk.get('source', '')}")
                parts.append(f"    Type: {chunk.get('source_type', '')}")
                parts.append(f"    Date: {chunk.get('date', '')}")
        
        parts.append("")
        
        # Source grading summary
        tier_counts = self._count_tiers(graded_sources)
        parts.append(f"Source Quality: Tier1={tier_counts[1]}, Tier2={tier_counts[2]}, Tier3={tier_counts[3]}")
        parts.append("")
        
        # Quantitative analysis
        if quant_analysis:
            parts.append("Quantitative Analysis:")
            
            calcs = quant_analysis.get("calculations", [])
            if calcs:
                parts.append("  Key Calculations:")
                for calc in calcs[:5]:
                    parts.append(f"    - {calc.get('metric', '')}: {calc.get('result', 'N/A')} ({calc.get('interpretation', '')})")
            
            insights = quant_analysis.get("key_insights", [])
            if insights:
                parts.append("  Key Insights:")
                for insight in insights[:5]:
                    parts.append(f"    - {insight}")
        
        return "\n".join(parts)
    
    def _format_sources_for_revision(self, graded_sources: List[Dict]) -> str:
        """Format graded sources for revision context."""
        if not graded_sources:
            return "No sources available."
        
        lines = []
        for source in graded_sources[:20]:  # Limit to prevent overflow
            lines.append(f"- [{source.get('source_id', '')}] {source.get('source', '')} (Tier {source.get('tier', 'N/A')})")
        
        return "\n".join(lines)
    
    def _format_quant_for_revision(self, quant_analysis: Optional[Dict]) -> str:
        """Format quantitative analysis for revision context."""
        if not quant_analysis:
            return "No quantitative analysis available."
        
        insights = quant_analysis.get("key_insights", [])
        return "\n".join(f"- {insight}" for insight in insights[:5])
    
    def _count_tiers(self, graded_sources: List[Dict]) -> Dict[int, int]:
        """Count sources by tier."""
        counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
        for source in graded_sources:
            tier = source.get("tier", 6)
            counts[tier] = counts.get(tier, 0) + 1
        return counts
    
    def _post_process_report(self, report: WriterOutput, graded_sources: List[Dict]) -> WriterOutput:
        """Post-process report to add metadata and validate."""
        
        # Estimate word count if not provided
        if report.word_count == 0:
            content = report.main_content + report.executive_summary
            report.word_count = len(content.split())
        
        # Count citations in text (basic heuristic)
        if report.citations_count == 0:
            import re
            citation_pattern = r'\[([^\]]+),\s*Tier\s*\d+\]'
            citations = re.findall(citation_pattern, report.main_content)
            report.citations_count = len(citations)
        
        # Count Tier 1-2 citations
        if report.tier_1_2_citations == 0:
            import re
            tier_12_pattern = r'\[([^\]]+),\s*Tier\s*[12]\]'
            tier_12_citations = re.findall(tier_12_pattern, report.main_content)
            report.tier_1_2_citations = len(tier_12_citations)
        
        # Extract sections
        if not report.sections_written:
            import re
            section_pattern = r'^#+\s+(.+)$'
            sections = re.findall(section_pattern, report.main_content, re.MULTILINE)
            report.sections_written = sections
        
        return report


# Standalone function for graph integration
async def run_writer_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run writer agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict with draft report
    """
    from app.services.llm import get_llm_client
    
    llm_client = get_llm_client()
    agent = WriterAgent(llm_client=llm_client)
    
    result = await agent.run(state)
    
    return {**state, **result}
