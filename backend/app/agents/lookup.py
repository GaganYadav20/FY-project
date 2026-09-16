"""
Lookup Agent - Single-agent path for simple factual queries.

Handles quick lookups like current rates, prices, NAV, simple definitions.
Uses tools for live data, never relies on model memory for time-sensitive info.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.prompts.lookup import LOOKUP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LookupResponse(BaseModel):
    """Structured response from Lookup Agent."""
    answer: str = Field(..., description="Direct answer to the query")
    source: Optional[str] = Field(None, description="Data source used")
    data_date: Optional[str] = Field(None, description="Date of data")
    confidence: str = Field("high", description="Confidence level: high/medium/low")
    needs_escalation: bool = Field(False, description="Query too complex for simple lookup")
    tool_results_used: List[str] = Field(default_factory=list, description="Tools called")


class LookupAgent:
    """Simple lookup agent for factual queries."""
    
    def __init__(self, llm_client, tools: Optional[Dict[str, Any]] = None):
        """
        Initialize Lookup Agent.
        
        Args:
            llm_client: LLM client for query processing
            tools: Dictionary of available tools (NSE, mutual fund NAV, etc.)
        """
        self.llm = llm_client
        self.tools = tools or {}
        
    async def run(self, query: str, state: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute lookup for simple query.
        
        Args:
            query: User query
            state: Optional state dict with context
            
        Returns:
            Dict with answer and metadata
        """
        logger.info(f"Lookup Agent processing: {query}")
        
        try:
            # Step 1: Classify what kind of lookup is needed
            lookup_type = await self._classify_lookup_type(query)
            logger.info(f"Lookup type classified as: {lookup_type}")
            
            # Step 2: Execute appropriate tool calls
            tool_results = await self._execute_tools(query, lookup_type)
            
            # Step 3: Generate answer using LLM with tool results
            response = await self._generate_answer(query, tool_results)
            
            # Step 4: Structure and return
            return {
                "answer": response.answer,
                "source": response.source,
                "data_date": response.data_date,
                "confidence": response.confidence,
                "needs_escalation": response.needs_escalation,
                "tool_results_used": response.tool_results_used,
                "tool_results": tool_results,  # Include raw tool results for visualization
                "tier": "simple",
                "current_stage": "lookup_complete"
            }
            
        except Exception as exc:
            logger.error(f"Lookup Agent failed: {exc}", exc_info=True)
            return {
                "answer": f"Unable to process lookup: {str(exc)}",
                "source": None,
                "confidence": "low",
                "needs_escalation": True,
                "errors": [str(exc)],
                "tier": "simple",
                "current_stage": "lookup_failed"
            }
    
    async def _classify_lookup_type(self, query: str) -> str:
        """
        Classify the type of lookup needed.
        
        Returns:
            One of: stock_price, nav, interest_rate, definition, comparison, general
        """
        q_lower = query.lower()
        
        # Check for comparison queries
        if any(term in q_lower for term in ["diff", "difference", "between", "vs", "versus", "compare"]):
            return "comparison"
        
        # Simple keyword-based classification
        if any(term in q_lower for term in ["nav", "net asset value", "mutual fund"]):
            return "nav"
        elif any(term in q_lower for term in ["stock price", "share price", "nse", "bse", "ticker"]):
            return "stock_price"
        elif any(term in q_lower for term in ["interest rate", "home loan", "fd rate", "repo rate", "loan rate"]):
            return "interest_rate"
        elif any(term in q_lower for term in ["what is", "define", "meaning", "explain", "ebitda", "ratio"]):
            return "definition"
        else:
            return "general"
    
    async def _handle_comparison(self, query: str) -> List[Dict]:
        """
        Handle simple comparison queries like "diff between RBI and SEBI".
        
        Returns:
            Tool results (empty for comparisons, will use LLM directly)
        """
        # For comparisons, we don't need tool calls
        # The LLM will provide the comparison directly
        return []
    
    async def _execute_tools(self, query: str, lookup_type: str) -> List[Dict[str, Any]]:
        """
        Execute appropriate tools based on lookup type.
        
        Args:
            query: User query
            lookup_type: Type of lookup (stock_price, nav, etc.)
            
        Returns:
            List of tool results
        """
        results = []
        
        try:
            if lookup_type == "comparison":
                # Handle simple comparisons directly
                return await self._handle_comparison(query)
            
            elif lookup_type == "nav" and "mutual_fund_nav" in self.tools:
                # Extract fund name from query
                fund_name = self._extract_fund_name(query)
                if fund_name:
                    tool_func = self.tools["mutual_fund_nav"]
                    result = await tool_func(fund_name=fund_name)
                    results.append({
                        "tool": "mutual_fund_nav",
                        "result": result,
                        "status": "success"
                    })
                    
            elif lookup_type == "stock_price" and "nse_stock_price" in self.tools:
                # Extract ticker symbol
                ticker = self._extract_ticker(query)
                if ticker:
                    tool_func = self.tools["nse_stock_price"]
                    result = await tool_func(symbol=ticker)
                    results.append({
                        "tool": "nse_stock_price",
                        "result": result,
                        "status": "success"
                    })
                    
            elif lookup_type == "interest_rate" and "bank_rates" in self.tools:
                tool_func = self.tools["bank_rates"]
                result = await tool_func(query=query)
                results.append({
                    "tool": "bank_rates",
                    "result": result,
                    "status": "success"
                })
                
            # If no specific tool matched or available, try web search
            if not results and "web_search" in self.tools:
                tool_func = self.tools["web_search"]
                result = await tool_func(query=query, max_results=3)
                results.append({
                    "tool": "web_search",
                    "result": result,
                    "status": "success"
                })
                
        except Exception as exc:
            logger.warning(f"Tool execution failed: {exc}")
            results.append({
                "tool": lookup_type,
                "result": None,
                "status": "failed",
                "error": str(exc)
            })
        
        return results
    
    async def _generate_answer(self, query: str, tool_results: List[Dict]) -> LookupResponse:
        """
        Generate final answer using LLM with tool results.
        
        Args:
            query: Original query
            tool_results: Results from tool executions
            
        Returns:
            Structured LookupResponse
        """
        # Format tool results for LLM
        tools_summary = self._format_tool_results(tool_results)
        
        # Build prompt
        user_prompt = f"""User Query: {query}

Verified Real-Time Tool & Search Data:
{tools_summary}

Instructions for Your Response:
1. Provide a comprehensive, in-depth, and well-structured financial response answering all dimensions of the query.
2. Structure your answer clearly using Markdown:
   - **Executive Overview**: High-level summary of the decision, rates, or financial topic.
   - **Key Policy Settings / Core Metrics**: Specific bullet points or structured table (e.g., Repo Rate, SDF, MSF, Bank Rate, Stance).
   - **Inflation, Growth & Market Outlook**: Detailed forecasts (e.g., CPI inflation targets, GDP projections, core vs headline data).
   - **Drivers & Policy Rationale**: Why this stance or situation exists (macroeconomic trends, supply-side factors, geopolitical/commodity impacts).
   - **Practical Implications**: Concrete real-world impact on borrowers (loan EMIs), savers (FDs/yields), businesses, and capital markets.
3. Use all factual data, percentages, dates, and numbers accurately from the provided tool results.
4. Maintain a professional, authoritative, and analytical tone with clear headings and bullet points."""

        try:
            # Call LLM with ChatGroq
            prompt_text = f"{LOOKUP_SYSTEM_PROMPT}\n\n{user_prompt}"
            response_raw = await self.llm.ainvoke(prompt_text)
            
            response_text = response_raw.content if hasattr(response_raw, 'content') else str(response_raw)
            response_text = response_text.strip()

            # If response is formatted as JSON, try to extract 'answer', otherwise use the full formatted markdown
            answer_content = response_text
            source_info = "Official Financial Releases & Real-Time Data"
            if response_text.startswith("{") and response_text.endswith("}"):
                try:
                    import json
                    parsed = json.loads(response_text)
                    answer_content = parsed.get("answer", response_text)
                    source_info = parsed.get("source", source_info)
                except Exception:
                    pass

            response_data = {
                "answer": answer_content,
                "source": source_info,
                "confidence": "high",
                "needs_escalation": False,
                "tool_results_used": [r["tool"] for r in tool_results if r.get("status") == "success"]
            }
            
            return LookupResponse(**response_data)
            
        except Exception as exc:
            logger.error(f"LLM call failed in lookup: {exc}")
            return LookupResponse(
                answer=f"Unable to process query: {str(exc)}",
                confidence="low",
                needs_escalation=True,
                tool_results_used=[]
            )
    
    def _format_tool_results(self, tool_results: List[Dict]) -> str:
        """Format tool results into readable text for LLM."""
        if not tool_results:
            return "No tool results available."
        
        formatted = []
        for result in tool_results:
            tool_name = result.get("tool", "unknown")
            status = result.get("status", "unknown")
            
            if status == "success":
                data = result.get("result", {})
                formatted.append(f"[{tool_name}] Success: {data}")
            else:
                error = result.get("error", "Unknown error")
                formatted.append(f"[{tool_name}] Failed: {error}")
        
        return "\n".join(formatted)
    
    def _extract_fund_name(self, query: str) -> Optional[str]:
        """Extract mutual fund name from query (basic implementation)."""
        # This is a simple implementation - could be enhanced with NER
        q_lower = query.lower()
        
        # Common fund name patterns
        if "axis" in q_lower and "bluechip" in q_lower:
            return "Axis Bluechip Fund"
        elif "hdfc" in q_lower and "top 100" in q_lower:
            return "HDFC Top 100 Fund"
        elif "sbi" in q_lower and "small cap" in q_lower:
            return "SBI Small Cap Fund"
        
        # Extract words after "NAV of" or "nav of"
        import re
        pattern = r"nav\s+of\s+([a-zA-Z\s]+?)(?:\?|$|\s+fund)"
        match = re.search(pattern, q_lower)
        if match:
            return match.group(1).strip().title() + " Fund"
        
        return None
    
    def _extract_ticker(self, query: str) -> Optional[str]:
        """Extract stock ticker from query (basic implementation)."""
        # Common Indian stock tickers
        common_tickers = {
            "reliance": "RELIANCE",
            "tcs": "TCS",
            "infosys": "INFY",
            "hdfc bank": "HDFCBANK",
            "icici bank": "ICICIBANK",
            "sbi": "SBIN",
            "wipro": "WIPRO",
            "itc": "ITC"
        }
        
        q_lower = query.lower()
        for company, ticker in common_tickers.items():
            if company in q_lower:
                return ticker
        
        # Look for explicit ticker symbols (all caps words)
        import re
        pattern = r'\b([A-Z]{2,10})\b'
        matches = re.findall(pattern, query)
        if matches:
            return matches[0]
        
        return None


# Standalone function for graph integration
async def run_lookup_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run lookup agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict
    """
    from app.services.llm import get_llm_client
    
    query = state.get("raw_query") or state.get("query_text", "")
    
    # Initialize agent
    llm_client = get_llm_client()
    
    # Get tools from state or initialize empty
    tools = state.get("tools", {})
    
    agent = LookupAgent(llm_client=llm_client, tools=tools)
    
    # Run lookup
    result = await agent.run(query=query, state=state)
    
    # Merge result into state
    return {
        **state,
        **result,
        "final_answer": result["answer"],
        "lookup_executed": True
    }
