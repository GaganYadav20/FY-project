"""
Quant Analysis Agent - Quantitative financial analysis and computations.

Performs financial ratio calculations, trend analysis, comparisons, and statistical analysis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.prompts.quant import QUANT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class Calculation(BaseModel):
    """Single calculation result."""
    metric: str = Field(..., description="Metric name (e.g., ROE, P/E Ratio)")
    formula: str = Field("", description="Formula used")
    inputs: Dict[str, float] = Field(default_factory=dict, description="Input values")
    result: Optional[float] = Field(None, description="Calculated result")
    interpretation: str = Field("", description="What this result means")
    entity: Optional[str] = Field(None, description="Entity this applies to (for comparisons)")


class Trend(BaseModel):
    """Trend analysis result."""
    metric: str = Field(..., description="Metric being analyzed")
    period: str = Field(..., description="Time period (e.g., FY2021-FY2023)")
    values: List[float] = Field(default_factory=list, description="Values over time")
    trend: str = Field("", description="Trend direction: upward/downward/stable")
    growth_rate: str = Field("", description="Growth rate description")
    interpretation: str = Field("", description="Analysis of the trend")


class Comparison(BaseModel):
    """Comparative analysis result."""
    metric: str = Field(..., description="Metric being compared")
    entities: Dict[str, float] = Field(default_factory=dict, description="Entity: Value mapping")
    interpretation: str = Field("", description="Comparative interpretation")


class QuantAnalysis(BaseModel):
    """Complete quantitative analysis output."""
    calculations: List[Calculation] = Field(default_factory=list)
    trends: List[Trend] = Field(default_factory=list)
    comparisons: List[Comparison] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    data_quality_notes: List[str] = Field(default_factory=list)


class QuantAgent:
    """Quantitative analysis agent."""
    
    def __init__(self, llm_client):
        """Initialize Quant Agent."""
        self.llm = llm_client
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform quantitative analysis on search results.
        
        Args:
            state: Workflow state with search results
            
        Returns:
            Updated state with quant analysis
        """
        logger.info("Quant Analysis Agent executing...")
        
        try:
            search_results = state.get("search_results", [])
            research_plan = state.get("research_plan", {})
            
            if not search_results:
                logger.warning("No search results available for quant analysis")
                return {
                    "quant_analysis": None,
                    "current_stage": "quant_skipped",
                    "warnings": ["No data available for quantitative analysis"]
                }
            
            # Extract numerical data from search results
            numerical_data = self._extract_numerical_data(search_results)
            
            if not numerical_data:
                logger.info("No numerical data found for quant analysis")
                return {
                    "quant_analysis": None,
                    "current_stage": "quant_skipped",
                    "warnings": ["No numerical data found in search results"]
                }
            
            # Perform analysis
            analysis = await self._perform_analysis(
                numerical_data=numerical_data,
                research_goal=research_plan.get("research_goal", ""),
                sub_questions=state.get("sub_questions", [])
            )
            
            logger.info(f"Quant analysis complete: {len(analysis.calculations)} calculations, "
                       f"{len(analysis.trends)} trends, {len(analysis.comparisons)} comparisons")
            
            return {
                "quant_analysis": analysis.dict(),
                "current_stage": "quant_complete",
                "numerical_insights_count": len(analysis.key_insights)
            }
            
        except Exception as exc:
            logger.error(f"Quant Analysis Agent failed: {exc}", exc_info=True)
            return {
                "quant_analysis": None,
                "current_stage": "quant_failed",
                "errors": [f"Quant analysis failed: {str(exc)}"]
            }
    
    def _extract_numerical_data(self, search_results: List[Dict]) -> Dict[str, Any]:
        """
        Extract numerical data from search results.
        
        Args:
            search_results: List of search result dicts
            
        Returns:
            Dict of extracted numerical data
        """
        numerical_data = {
            "metrics": [],
            "time_series": [],
            "entities": {}
        }
        
        import re
        
        for result in search_results:
            chunks = result.get("retrieved_chunks", [])
            
            for chunk in chunks:
                content = chunk.get("content", "")
                
                # Extract numbers with context
                # Pattern: word/phrase + number + unit
                patterns = [
                    r'(\w+(?:\s+\w+)?)\s*:?\s*([\d,]+\.?\d*)\s*(%|cr|crore|lakh|₹|Rs)',
                    r'(revenue|profit|margin|ratio|rate|nav|price)\s*:?\s*([\d,]+\.?\d*)',
                ]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        metric_name = match.group(1).strip()
                        value_str = match.group(2).replace(',', '')
                        
                        try:
                            value = float(value_str)
                            numerical_data["metrics"].append({
                                "name": metric_name,
                                "value": value,
                                "source": chunk.get("source", ""),
                                "date": chunk.get("date", "")
                            })
                        except ValueError:
                            continue
        
        return numerical_data
    
    async def _perform_analysis(
        self,
        numerical_data: Dict[str, Any],
        research_goal: str,
        sub_questions: List[str]
    ) -> QuantAnalysis:
        """
        Perform quantitative analysis using LLM.
        
        Args:
            numerical_data: Extracted numerical data
            research_goal: Research objective
            sub_questions: List of sub-questions
            
        Returns:
            QuantAnalysis object
        """
        # Format data for LLM
        data_summary = self._format_data_summary(numerical_data)
        
        user_prompt = f"""Research Goal: {research_goal}

Available Numerical Data:
{data_summary}

Perform quantitative analysis:
1. Calculate relevant financial metrics and ratios
2. Identify trends if time-series data is available
3. Perform comparisons if multiple entities present
4. Generate key insights

Rules:
- Only use provided data (never fabricate numbers)
- Show formulas and inputs for all calculations
- Interpret results in financial context
- Flag any data quality issues

Return structured JSON."""

        try:
            response = await self.llm.call(
                system_prompt=QUANT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_schema=QuantAnalysis
            )
            
            return QuantAnalysis(**response)
            
        except Exception as exc:
            logger.error(f"Quant analysis LLM call failed: {exc}")
            # Return minimal analysis
            return QuantAnalysis(
                calculations=[],
                trends=[],
                comparisons=[],
                key_insights=[],
                data_quality_notes=[f"Analysis failed: {str(exc)}"]
            )
    
    def _format_data_summary(self, numerical_data: Dict[str, Any]) -> str:
        """Format numerical data for LLM consumption."""
        lines = []
        
        metrics = numerical_data.get("metrics", [])
        if metrics:
            lines.append("Extracted Metrics:")
            for m in metrics[:20]:  # Limit to avoid token overflow
                lines.append(f"  - {m['name']}: {m['value']} (Source: {m.get('source', 'Unknown')}, Date: {m.get('date', 'Unknown')})")
        
        if not lines:
            return "No numerical data extracted."
        
        return "\n".join(lines)


# Standalone function for graph integration
async def run_quant_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run quant agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict with quant analysis
    """
    from app.services.llm import get_llm_client
    
    llm_client = get_llm_client()
    agent = QuantAgent(llm_client=llm_client)
    
    result = await agent.run(state)
    
    return {**state, **result}
