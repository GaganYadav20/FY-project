"""
Source Tier Agent - Evidence grading and source authority ranking.

Grades sources by authority using FinTech-specific evidence hierarchy.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.prompts.source_tier import SOURCE_TIER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GradedSource(BaseModel):
    """Single graded source."""
    source_id: str = Field(..., description="Identifier for this source")
    source: str = Field(..., description="URL or source name")
    source_type: str = Field(..., description="Type of source")
    tier: int = Field(..., description="Tier 1-7 based on hierarchy")
    authority_score: float = Field(..., description="Authority score 0-1")
    reliability_factors: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    verification_needed: bool = Field(False)
    quality_flags: List[str] = Field(default_factory=list)


class EvidenceSummary(BaseModel):
    """Summary of evidence quality."""
    tier_1_sources: int = 0
    tier_2_sources: int = 0
    tier_3_sources: int = 0
    tier_4_7_sources: int = 0
    overall_evidence_quality: str = "unknown"
    verification_gaps: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class SourceTierResult(BaseModel):
    """Complete source tier grading output."""
    graded_sources: List[GradedSource] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)


class SourceTierAgent:
    """Source tier grading agent."""
    
    # Tier classification rules
    TIER_RULES = {
        1: {
            "keywords": ["rbi.org", "sebi.gov", "nseindia.com", "bseindia.com", "official exchange"],
            "types": ["regulatory_filing", "exchange_data", "api_data"],
            "score_range": (0.9, 1.0)
        },
        2: {
            "keywords": ["annual report", "quarterly", "earnings", "investor presentation"],
            "types": ["company_filing", "annual_report", "earnings_call"],
            "score_range": (0.75, 0.89)
        },
        3: {
            "keywords": ["economictimes", "moneycontrol", "bloomberg", "reuters", "business-standard"],
            "types": ["news_article", "financial_news"],
            "score_range": (0.6, 0.74)
        },
        4: {
            "keywords": ["research report", "analyst", "kpmg", "deloitte", "academic"],
            "types": ["analyst_report", "research_paper"],
            "score_range": (0.5, 0.59)
        },
        5: {
            "keywords": ["bankbazaar", "paisabazaar", "rate aggregator"],
            "types": ["rate_aggregator", "comparison_platform"],
            "score_range": (0.4, 0.49)
        },
        6: {
            "keywords": ["blog", "opinion", "general news"],
            "types": ["blog", "general_news"],
            "score_range": (0.2, 0.39)
        },
        7: {
            "keywords": ["twitter", "reddit", "forum", "social"],
            "types": ["social_media", "forum"],
            "score_range": (0.0, 0.19)
        }
    }
    
    def __init__(self, llm_client):
        """Initialize Source Tier Agent."""
        self.llm = llm_client
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Grade all sources from search results.
        
        Args:
            state: Workflow state with search results
            
        Returns:
            Updated state with graded sources
        """
        logger.info("Source Tier Agent executing...")
        
        try:
            search_results = state.get("search_results", [])
            
            if not search_results:
                logger.warning("No search results to grade")
                return {
                    "graded_sources": [],
                    "evidence_summary": EvidenceSummary().dict(),
                    "current_stage": "source_tier_skipped"
                }
            
            # Grade all sources
            all_graded = []
            source_id_counter = 0
            
            for result in search_results:
                chunks = result.get("retrieved_chunks", [])
                
                for chunk in chunks:
                    source_id = f"source_{source_id_counter}"
                    source_id_counter += 1
                    
                    graded = self._grade_source(chunk, source_id)
                    all_graded.append(graded)
            
            # Generate evidence summary
            summary = self._generate_summary(all_graded)
            
            logger.info(f"Graded {len(all_graded)} sources: "
                       f"Tier1={summary.tier_1_sources}, Tier2={summary.tier_2_sources}, "
                       f"Tier3={summary.tier_3_sources}")
            
            return {
                "graded_sources": [g.dict() for g in all_graded],
                "evidence_summary": summary.dict(),
                "current_stage": "source_tier_complete"
            }
            
        except Exception as exc:
            logger.error(f"Source Tier Agent failed: {exc}", exc_info=True)
            return {
                "graded_sources": [],
                "evidence_summary": EvidenceSummary().dict(),
                "current_stage": "source_tier_failed",
                "errors": [f"Source tier grading failed: {str(exc)}"]
            }
    
    def _grade_source(self, chunk: Dict[str, Any], source_id: str) -> GradedSource:
        """
        Grade a single source chunk.
        
        Args:
            chunk: Retrieved chunk dict
            source_id: Unique identifier
            
        Returns:
            GradedSource object
        """
        source = chunk.get("source", "")
        source_type = chunk.get("source_type", "unknown")
        date = chunk.get("date", "")
        
        # Determine tier using rule-based classification
        tier = self._classify_tier(source, source_type)
        
        # Calculate authority score
        score_range = self.TIER_RULES[tier]["score_range"]
        base_score = (score_range[0] + score_range[1]) / 2
        
        # Adjust score based on recency
        adjusted_score = self._adjust_for_recency(base_score, date)
        
        # Generate reliability factors and limitations
        reliability_factors = self._get_reliability_factors(tier, source_type)
        limitations = self._get_limitations(tier, source_type, date)
        
        # Determine if verification needed
        verification_needed = tier >= 3
        
        # Quality flags
        quality_flags = self._get_quality_flags(tier, date, source_type)
        
        return GradedSource(
            source_id=source_id,
            source=source,
            source_type=source_type,
            tier=tier,
            authority_score=adjusted_score,
            reliability_factors=reliability_factors,
            limitations=limitations,
            verification_needed=verification_needed,
            quality_flags=quality_flags
        )
    
    def _classify_tier(self, source: str, source_type: str) -> int:
        """Classify source into tier 1-7."""
        source_lower = source.lower()
        type_lower = source_type.lower()
        
        # Check each tier's rules
        for tier, rules in self.TIER_RULES.items():
            # Check by keywords in source URL/name
            if any(keyword in source_lower for keyword in rules["keywords"]):
                return tier
            
            # Check by source type
            if type_lower in [t.lower() for t in rules["types"]]:
                return tier
        
        # Default to tier 6 (general news/blog)
        return 6
    
    def _adjust_for_recency(self, base_score: float, date: str) -> float:
        """Adjust authority score based on date recency."""
        if not date:
            return base_score
        
        try:
            from datetime import datetime, timedelta
            source_date = datetime.strptime(date, "%Y-%m-%d")
            now = datetime.now()
            age_days = (now - source_date).days
            
            # Downgrade for old data
            if age_days > 365:  # >1 year
                return max(0.0, base_score - 0.2)
            elif age_days > 90:  # >3 months
                return max(0.0, base_score - 0.1)
            
            return base_score
            
        except:
            return base_score
    
    def _get_reliability_factors(self, tier: int, source_type: str) -> List[str]:
        """Get reliability factors for a tier."""
        factors = {
            1: ["Official regulatory/exchange source", "Primary authoritative data", "Legally binding"],
            2: ["Audited company data", "Official company communication", "Regulatory filing requirements"],
            3: ["Established financial media", "Professional journalism standards", "Editorial oversight"],
            4: ["Professional analysis", "Subject matter expertise", "Research methodology"],
            5: ["Aggregated data", "Multiple source compilation", "Comparison utility"],
            6: ["General information", "Opinion/commentary", "Secondary source"],
            7: ["User-generated content", "Unverified information", "Anecdotal"]
        }
        return factors.get(tier, ["Unknown reliability"])
    
    def _get_limitations(self, tier: int, source_type: str, date: str) -> List[str]:
        """Get limitations for a tier."""
        limitations = []
        
        if tier >= 3:
            limitations.append("Secondary source, not primary data")
        
        if tier >= 5:
            limitations.append("Requires verification from higher-tier source")
        
        if tier == 7:
            limitations.append("Not suitable for factual claims")
            limitations.append("High risk of misinformation")
        
        # Date-based limitations
        if date:
            try:
                from datetime import datetime
                source_date = datetime.strptime(date, "%Y-%m-%d")
                age_days = (datetime.now() - source_date).days
                
                if age_days > 90:
                    limitations.append(f"Data is {age_days} days old; verify for current accuracy")
            except:
                pass
        
        return limitations
    
    def _get_quality_flags(self, tier: int, date: str, source_type: str) -> List[str]:
        """Get quality flags for source."""
        flags = []
        
        if tier <= 2:
            flags.append("verified")
        elif tier <= 4:
            flags.append("unverified")
        else:
            flags.append("weak")
        
        # Check recency
        if date:
            try:
                from datetime import datetime
                source_date = datetime.strptime(date, "%Y-%m-%d")
                age_days = (datetime.now() - source_date).days
                
                if age_days > 30:
                    flags.append("stale")
            except:
                pass
        
        return flags
    
    def _generate_summary(self, graded_sources: List[GradedSource]) -> EvidenceSummary:
        """Generate evidence quality summary."""
        tier_counts = {1: 0, 2: 0, 3: 0}
        tier_4_7 = 0
        
        for source in graded_sources:
            if source.tier == 1:
                tier_counts[1] += 1
            elif source.tier == 2:
                tier_counts[2] += 1
            elif source.tier == 3:
                tier_counts[3] += 1
            else:
                tier_4_7 += 1
        
        # Determine overall quality
        total = len(graded_sources)
        if total == 0:
            overall_quality = "unknown"
        elif tier_counts[1] + tier_counts[2] >= total * 0.6:
            overall_quality = "high"
        elif tier_counts[1] + tier_counts[2] + tier_counts[3] >= total * 0.5:
            overall_quality = "moderate"
        else:
            overall_quality = "low"
        
        # Identify verification gaps
        gaps = []
        if tier_counts[1] == 0 and tier_counts[2] == 0:
            gaps.append("No Tier 1-2 authoritative sources; all claims need verification")
        
        weak_sources = [s for s in graded_sources if s.tier >= 6]
        if weak_sources:
            gaps.append(f"{len(weak_sources)} sources are Tier 6-7 (weak evidence)")
        
        # Recommendations
        recommendations = []
        if tier_counts[1] > 0:
            recommendations.append(f"Strong evidence from {tier_counts[1]} Tier 1 source(s)")
        
        if tier_4_7 > total * 0.5:
            recommendations.append("Consider upgrading to higher-tier sources where possible")
        
        return EvidenceSummary(
            tier_1_sources=tier_counts[1],
            tier_2_sources=tier_counts[2],
            tier_3_sources=tier_counts[3],
            tier_4_7_sources=tier_4_7,
            overall_evidence_quality=overall_quality,
            verification_gaps=gaps,
            recommendations=recommendations
        )


# Standalone function for graph integration
async def run_source_tier_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run source tier agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict with graded sources
    """
    from app.services.llm import get_llm_client
    
    llm_client = get_llm_client()
    agent = SourceTierAgent(llm_client=llm_client)
    
    result = await agent.run(state)
    
    return {**state, **result}
