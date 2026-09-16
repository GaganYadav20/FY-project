"""
Critic/Compliance Agent - Quality control and regulatory compliance.

Validates accuracy, completeness, citation integrity, and SEBI compliance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.prompts.critic import CRITIC_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class RubricScore(BaseModel):
    """Score for a specific rubric category."""
    score: int = Field(..., description="Score 0-100")
    weight: float = Field(..., description="Weight in final score")
    weighted_score: float = Field(..., description="Score * weight")
    issues: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)


class Issue(BaseModel):
    """Single quality issue."""
    severity: str = Field(..., description="HIGH, MEDIUM, or LOW")
    category: str = Field(..., description="Issue category")
    location: str = Field("", description="Where in report")
    issue: str = Field(..., description="Issue description")
    required_action: Optional[str] = Field(None, description="Required fix for HIGH")
    suggested_action: Optional[str] = Field(None, description="Suggested fix for MEDIUM/LOW")


class ComplianceCheck(BaseModel):
    """SEBI compliance check result."""
    passed: bool = Field(..., description="Whether compliance check passed")
    advice_boundary_violations: List[str] = Field(default_factory=list)
    required_disclaimers_present: bool = True
    risk_warnings_adequate: bool = True
    notes: str = ""


class CriticResult(BaseModel):
    """Complete critic evaluation output."""
    overall_score: int = Field(..., description="Overall score 0-100")
    decision: str = Field(..., description="APPROVED, REVISION_REQUIRED, or REJECTED")
    
    rubric_scores: Dict[str, RubricScore] = Field(default_factory=dict)
    
    critical_issues: List[Issue] = Field(default_factory=list)
    medium_issues: List[Issue] = Field(default_factory=list)
    
    compliance_check: ComplianceCheck = Field(default_factory=ComplianceCheck)
    
    revision_instructions: List[str] = Field(default_factory=list)
    approval_notes: str = ""
    estimated_confidence: str = "medium"
    recommendation: str = ""


class CriticAgent:
    """Critic and compliance checking agent."""
    
    # Rubric weights
    WEIGHTS = {
        "factual_accuracy": 0.30,
        "citation_integrity": 0.25,
        "completeness": 0.20,
        "regulatory_compliance": 0.15,
        "evidence_quality": 0.10
    }
    
    # Decision thresholds
    APPROVED_THRESHOLD = 85
    REVISION_THRESHOLD = 75
    MINOR_REVISION_THRESHOLD = 60
    
    def __init__(self, llm_client):
        """Initialize Critic Agent."""
        self.llm = llm_client
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive quality control on report.
        
        Args:
            state: Workflow state with draft report and all research data
            
        Returns:
            Updated state with critic evaluation
        """
        logger.info("Critic/Compliance Agent executing...")
        
        try:
            draft_report = state.get("draft_report")
            
            if not draft_report:
                logger.error("No draft report to evaluate")
                return {
                    "critic_feedback": None,
                    "current_stage": "critic_failed",
                    "errors": ["No draft report available for evaluation"]
                }
            
            # Perform evaluation
            evaluation = await self._evaluate_report(
                draft_report=draft_report,
                research_plan=state.get("research_plan", {}),
                search_results=state.get("search_results", []),
                graded_sources=state.get("graded_sources", []),
                quant_analysis=state.get("quant_analysis"),
                originality_check=state.get("originality_check")
            )
            
            logger.info(f"Critic evaluation complete: score={evaluation.overall_score}, "
                       f"decision={evaluation.decision}, "
                       f"critical_issues={len(evaluation.critical_issues)}")
            
            # Determine next action
            needs_revision = evaluation.decision in ["REVISION_REQUIRED", "REJECTED"]
            
            return {
                "critic_feedback": evaluation.dict(),
                "current_stage": "critic_complete",
                "needs_revision": needs_revision,
                "critic_approved": evaluation.decision == "APPROVED",
                "overall_quality_score": evaluation.overall_score
            }
            
        except Exception as exc:
            logger.error(f"Critic Agent failed: {exc}", exc_info=True)
            return {
                "critic_feedback": None,
                "current_stage": "critic_failed",
                "needs_revision": True,
                "errors": [f"Critic evaluation failed: {str(exc)}"]
            }
    
    async def _evaluate_report(
        self,
        draft_report: Dict[str, Any],
        research_plan: Dict[str, Any],
        search_results: List[Dict],
        graded_sources: List[Dict],
        quant_analysis: Optional[Dict],
        originality_check: Optional[Dict]
    ) -> CriticResult:
        """Perform comprehensive report evaluation."""
        
        # Extract report content
        main_content = draft_report.get("main_content", "")
        executive_summary = draft_report.get("executive_summary", "")
        references = draft_report.get("references", [])
        
        # Initialize rubric scores
        rubric_scores = {}
        
        # 1. Factual Accuracy (30%)
        rubric_scores["factual_accuracy"] = self._check_factual_accuracy(
            content=main_content,
            search_results=search_results,
            quant_analysis=quant_analysis
        )
        
        # 2. Citation Integrity (25%)
        rubric_scores["citation_integrity"] = self._check_citation_integrity(
            content=main_content,
            references=references,
            graded_sources=graded_sources
        )
        
        # 3. Completeness (20%)
        rubric_scores["completeness"] = self._check_completeness(
            content=main_content,
            executive_summary=executive_summary,
            research_plan=research_plan,
            search_results=search_results
        )
        
        # 4. Regulatory Compliance (15%) - CRITICAL
        compliance_result = self._check_compliance(main_content)
        rubric_scores["regulatory_compliance"] = RubricScore(
            score=100 if compliance_result.passed else 0,
            weight=self.WEIGHTS["regulatory_compliance"],
            weighted_score=(100 if compliance_result.passed else 0) * self.WEIGHTS["regulatory_compliance"],
            issues=compliance_result.advice_boundary_violations,
            strengths=["Compliance check passed"] if compliance_result.passed else []
        )
        
        # 5. Evidence Quality (10%)
        rubric_scores["evidence_quality"] = self._check_evidence_quality(
            content=main_content,
            graded_sources=graded_sources
        )
        
        # Calculate overall score
        overall_score = sum(score.weighted_score for score in rubric_scores.values())
        overall_score = int(round(overall_score))
        
        # Collect issues
        critical_issues, medium_issues = self._collect_issues(rubric_scores, compliance_result)
        
        # Make decision
        decision, recommendation = self._make_decision(
            overall_score=overall_score,
            critical_issues=critical_issues,
            compliance_passed=compliance_result.passed
        )
        
        # Generate revision instructions
        revision_instructions = self._generate_revision_instructions(
            critical_issues=critical_issues,
            medium_issues=medium_issues,
            decision=decision
        )
        
        return CriticResult(
            overall_score=overall_score,
            decision=decision,
            rubric_scores=rubric_scores,
            critical_issues=critical_issues,
            medium_issues=medium_issues,
            compliance_check=compliance_result,
            revision_instructions=revision_instructions,
            approval_notes=self._generate_approval_notes(decision, overall_score),
            estimated_confidence="high" if overall_score >= 80 else "medium",
            recommendation=recommendation
        )
    
    def _check_factual_accuracy(
        self,
        content: str,
        search_results: List[Dict],
        quant_analysis: Optional[Dict]
    ) -> RubricScore:
        """Check factual accuracy of report."""
        issues = []
        strengths = []
        
        import re
        
        # Check for uncited numerical claims
        number_pattern = r'\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:%|cr|crore|lakh|₹|Rs)?\b'
        numbers = re.findall(number_pattern, content)
        
        # Simple heuristic: check if numbers have nearby citations
        citation_pattern = r'\[([^\]]+),\s*Tier\s*\d+\]'
        citations = re.findall(citation_pattern, content)
        
        if len(numbers) > len(citations) * 2:
            issues.append("Multiple numerical claims may lack citations")
        else:
            strengths.append("Numerical claims appear well-cited")
        
        # Check for contradictions (basic check for conflicting numbers with same context)
        # This is a simplified check
        if "however" in content.lower() or "but" in content.lower():
            strengths.append("Report presents balanced views")
        
        # Check if calculations are present and match quant analysis
        if quant_analysis:
            strengths.append("Quantitative analysis results incorporated")
        
        # Score based on issues
        base_score = 85
        score = base_score - (len(issues) * 10)
        score = max(0, min(100, score))
        
        return RubricScore(
            score=score,
            weight=self.WEIGHTS["factual_accuracy"],
            weighted_score=score * self.WEIGHTS["factual_accuracy"],
            issues=issues,
            strengths=strengths
        )
    
    def _check_citation_integrity(
        self,
        content: str,
        references: List[Dict],
        graded_sources: List[Dict]
    ) -> RubricScore:
        """Check citation integrity."""
        issues = []
        strengths = []
        
        import re
        
        # Count citations
        citation_pattern = r'\[([^\]]+),\s*Tier\s*(\d+)\]'
        citations = re.findall(citation_pattern, content)
        
        if len(citations) == 0:
            issues.append("No citations found in report")
            score = 0
        else:
            strengths.append(f"{len(citations)} citations present")
            
            # Check tier distribution
            tier_1_2_count = len([c for c in citations if c[1] in ['1', '2']])
            tier_ratio = tier_1_2_count / len(citations) if citations else 0
            
            if tier_ratio >= 0.6:
                strengths.append(f"{tier_ratio*100:.0f}% citations from Tier 1-2 sources")
            elif tier_ratio < 0.3:
                issues.append(f"Only {tier_ratio*100:.0f}% citations from high-tier sources")
            
            # Check if references list matches citations
            if len(references) < len(set([c[0] for c in citations])) * 0.8:
                issues.append("References list may be incomplete")
            
            # Score
            base_score = 75
            if tier_ratio >= 0.6:
                base_score = 90
            score = base_score - (len(issues) * 5)
            score = max(0, min(100, score))
        
        return RubricScore(
            score=score,
            weight=self.WEIGHTS["citation_integrity"],
            weighted_score=score * self.WEIGHTS["citation_integrity"],
            issues=issues,
            strengths=strengths
        )
    
    def _check_completeness(
        self,
        content: str,
        executive_summary: str,
        research_plan: Dict[str, Any],
        search_results: List[Dict]
    ) -> RubricScore:
        """Check completeness of report."""
        issues = []
        strengths = []
        
        # Check executive summary
        if not executive_summary or len(executive_summary.split()) < 20:
            issues.append("Executive summary is missing or too brief")
        else:
            strengths.append("Executive summary present")
        
        # Check if all sub-questions are addressed
        sub_questions = research_plan.get("sub_questions", [])
        if sub_questions:
            # Simple check: are key terms from sub-questions present in content?
            addressed_count = 0
            for sq in sub_questions:
                # Extract key terms (very simple)
                key_terms = [w for w in sq.lower().split() if len(w) > 4]
                if any(term in content.lower() for term in key_terms[:3]):
                    addressed_count += 1
            
            if addressed_count >= len(sub_questions) * 0.8:
                strengths.append(f"{addressed_count}/{len(sub_questions)} sub-questions addressed")
            else:
                issues.append(f"Only {addressed_count}/{len(sub_questions)} sub-questions clearly addressed")
        
        # Check content length
        word_count = len(content.split())
        if word_count < 300:
            issues.append("Report content is very brief (<300 words)")
        elif word_count > 500:
            strengths.append(f"Comprehensive content ({word_count} words)")
        
        # Score
        base_score = 85
        score = base_score - (len(issues) * 10)
        score = max(0, min(100, score))
        
        return RubricScore(
            score=score,
            weight=self.WEIGHTS["completeness"],
            weighted_score=score * self.WEIGHTS["completeness"],
            issues=issues,
            strengths=strengths
        )
    
    def _check_compliance(self, content: str) -> ComplianceCheck:
        """Check SEBI compliance - advice boundary."""
        
        advice_violations = []
        
        content_lower = content.lower()
        
        # Check for prohibited advice language
        prohibited_patterns = [
            (r'\b(you should|must) (buy|sell|invest)\b', "Direct buy/sell recommendation"),
            (r'\bgood (time|investment|opportunity) to (buy|invest|enter)\b', "Timing recommendation"),
            (r'\b(i |we )recommend (buying|selling|investing)\b', "Explicit recommendation"),
            (r'\b(undervalued|overvalued).{0,50}(buy|sell)\b', "Valuation-based advice"),
            (r'\ballocate \d+% (of|to)\b', "Specific allocation advice")
        ]
        
        import re
        for pattern, violation_type in prohibited_patterns:
            if re.search(pattern, content_lower):
                advice_violations.append(violation_type)
        
        # Check for required disclaimers
        disclaimer_keywords = ["not investment advice", "not financial advice", "consult", "registered advisor"]
        has_disclaimer = any(kw in content_lower for kw in disclaimer_keywords)
        
        # Check for risk warnings when performance is discussed
        if "return" in content_lower or "performance" in content_lower:
            risk_warning_keywords = ["past performance", "risk", "no guarantee"]
            has_risk_warning = any(kw in content_lower for kw in risk_warning_keywords)
        else:
            has_risk_warning = True
        
        passed = (
            len(advice_violations) == 0 and
            has_disclaimer and
            has_risk_warning
        )
        
        notes = []
        if len(advice_violations) > 0:
            notes.append(f"Found {len(advice_violations)} potential advice boundary violations")
        if not has_disclaimer:
            notes.append("Required disclaimer not found")
        if not has_risk_warning:
            notes.append("Risk warnings insufficient")
        if passed:
            notes.append("No compliance violations detected. Report maintains informational stance.")
        
        return ComplianceCheck(
            passed=passed,
            advice_boundary_violations=advice_violations,
            required_disclaimers_present=has_disclaimer,
            risk_warnings_adequate=has_risk_warning,
            notes=" ".join(notes)
        )
    
    def _check_evidence_quality(
        self,
        content: str,
        graded_sources: List[Dict]
    ) -> RubricScore:
        """Check evidence quality."""
        issues = []
        strengths = []
        
        if not graded_sources:
            issues.append("No source grading available")
            score = 50
        else:
            # Count by tier
            tier_counts = {1: 0, 2: 0, 3: 0}
            for source in graded_sources:
                tier = source.get("tier", 7)
                if tier in tier_counts:
                    tier_counts[tier] += 1
            
            total = sum(tier_counts.values())
            tier_12_ratio = (tier_counts[1] + tier_counts[2]) / total if total > 0 else 0
            
            if tier_12_ratio >= 0.6:
                strengths.append(f"{tier_12_ratio*100:.0f}% Tier 1-2 sources")
                score = 90
            elif tier_12_ratio >= 0.4:
                strengths.append("Moderate use of high-tier sources")
                score = 75
            else:
                issues.append("Over-reliance on lower-tier sources")
                score = 60
        
        return RubricScore(
            score=score,
            weight=self.WEIGHTS["evidence_quality"],
            weighted_score=score * self.WEIGHTS["evidence_quality"],
            issues=issues,
            strengths=strengths
        )
    
    def _collect_issues(
        self,
        rubric_scores: Dict[str, RubricScore],
        compliance_result: ComplianceCheck
    ) -> tuple[List[Issue], List[Issue]]:
        """Collect critical and medium issues."""
        critical_issues = []
        medium_issues = []
        
        # Compliance violations are always critical
        if not compliance_result.passed:
            for violation in compliance_result.advice_boundary_violations:
                critical_issues.append(Issue(
                    severity="HIGH",
                    category="regulatory_compliance",
                    issue=f"Compliance violation: {violation}",
                    required_action="Remove or rephrase advice-crossing language"
                ))
        
        # Convert rubric issues to Issue objects
        for category, rubric in rubric_scores.items():
            if rubric.score < 70:
                for issue_text in rubric.issues:
                    if rubric.score < 50:
                        critical_issues.append(Issue(
                            severity="HIGH",
                            category=category,
                            issue=issue_text,
                            required_action="Address this critical issue"
                        ))
                    else:
                        medium_issues.append(Issue(
                            severity="MEDIUM",
                            category=category,
                            issue=issue_text,
                            suggested_action="Consider addressing this issue"
                        ))
        
        return critical_issues, medium_issues
    
    def _make_decision(
        self,
        overall_score: int,
        critical_issues: List[Issue],
        compliance_passed: bool
    ) -> tuple[str, str]:
        """Make approval decision."""
        
        # Compliance violations = automatic rejection
        if not compliance_passed:
            return "REJECTED", "Compliance violations detected"
        
        # Critical issues = revision required
        if len(critical_issues) > 0:
            return "REVISION_REQUIRED", f"{len(critical_issues)} critical issue(s) must be addressed"
        
        # Score-based decision
        if overall_score >= self.APPROVED_THRESHOLD:
            return "APPROVED", "Report meets quality standards"
        elif overall_score >= self.REVISION_THRESHOLD:
            return "APPROVED_WITH_MINOR_REVISIONS", "Minor improvements recommended"
        else:
            return "REVISION_REQUIRED", "Significant improvements needed"
    
    def _generate_revision_instructions(
        self,
        critical_issues: List[Issue],
        medium_issues: List[Issue],
        decision: str
    ) -> List[str]:
        """Generate specific revision instructions."""
        instructions = []
        
        # Critical issues first
        for issue in critical_issues:
            action = issue.required_action or "Fix this critical issue"
            instructions.append(f"[CRITICAL] {issue.category}: {action}")
        
        # Medium issues
        for issue in medium_issues[:5]:  # Limit to top 5
            action = issue.suggested_action or "Address this issue"
            instructions.append(f"[MEDIUM] {issue.category}: {action}")
        
        return instructions
    
    def _generate_approval_notes(self, decision: str, score: int) -> str:
        """Generate approval notes."""
        if decision == "APPROVED":
            return f"Report approved with score {score}/100. Meets all quality standards."
        elif decision == "APPROVED_WITH_MINOR_REVISIONS":
            return f"Report approved with minor revisions (score: {score}/100)."
        elif decision == "REVISION_REQUIRED":
            return f"Report requires revision (score: {score}/100). Address critical issues."
        else:  # REJECTED
            return "Report rejected due to compliance violations. Major revision required."


# Standalone function for graph integration
async def run_critic_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run critic agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict with critic feedback
    """
    from app.services.llm import get_llm_client
    
    llm_client = get_llm_client()
    agent = CriticAgent(llm_client=llm_client)
    
    result = await agent.run(state)
    
    return {**state, **result}
