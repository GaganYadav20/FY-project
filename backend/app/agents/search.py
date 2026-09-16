"""
Search Agent - Multi-source search and retrieval.

Gathers information from NSE/BSE, mutual funds, news, web search, and vector store.
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.prompts.search import SEARCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    """Single retrieved information chunk."""
    content: str = Field(..., description="Retrieved text/data")
    source: str = Field(..., description="URL, API, or document name")
    source_type: str = Field(..., description="Type: regulatory_filing, news_article, api_data, etc.")
    date: Optional[str] = Field(None, description="Publication or retrieval date")
    relevance_score: float = Field(0.0, description="Relevance to sub-question (0-1)")
    key_facts: List[str] = Field(default_factory=list, description="Key information extracted")


class SearchResult(BaseModel):
    """Structured search results for a sub-question."""
    sub_question: str = Field(..., description="The sub-question being answered")
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list, description="Retrieved information")
    search_summary: str = Field("", description="Summary of search execution")
    data_quality: str = Field("unknown", description="Quality: high/medium/low/unknown")
    gaps: List[str] = Field(default_factory=list, description="Data gaps identified")
    retrieval_errors: List[str] = Field(default_factory=list, description="Any retrieval failures")


class SearchAgent:
    """Search agent for multi-source information retrieval."""
    
    def __init__(self, llm_client, tools: Optional[Dict[str, Any]] = None):
        """
        Initialize Search Agent.
        
        Args:
            llm_client: LLM client for processing
            tools: Dictionary of available tools
        """
        self.llm = llm_client
        self.tools = tools or {}
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute search for all sub-questions.
        
        Args:
            state: Current workflow state with sub_questions
            
        Returns:
            Updated state with search results
        """
        logger.info("Search Agent executing...")
        
        try:
            sub_questions = state.get("sub_questions", [])
            expected_sources = state.get("expected_sources", [])
            
            if not sub_questions:
                raise ValueError("No sub-questions provided to Search Agent")
            
            # Search for each sub-question in parallel for performance
            all_results = []
            if sub_questions:
                # Parallel execution of sub-questions
                search_tasks = [
                    self._search_sub_question(question, expected_sources)
                    for question in sub_questions
                ]
                all_results = await asyncio.gather(*search_tasks)
            
            # Aggregate results
            total_chunks = sum(len(r.retrieved_chunks) for r in all_results)
            total_errors = sum(len(r.retrieval_errors) for r in all_results)
            
            logger.info(f"Search complete: {total_chunks} chunks retrieved, {total_errors} errors")
            
            return {
                "search_results": [r.dict() for r in all_results],
                "total_chunks_retrieved": total_chunks,
                "current_stage": "search_complete",
                "search_errors": total_errors > 0
            }
            
        except Exception as exc:
            logger.error(f"Search Agent failed: {exc}", exc_info=True)
            return {
                "search_results": [],
                "total_chunks_retrieved": 0,
                "current_stage": "search_failed",
                "errors": [f"Search failed: {str(exc)}"]
            }
    
    async def _search_sub_question(
        self, 
        question: str, 
        expected_sources: List[str]
    ) -> SearchResult:
        """
        Search for a single sub-question across multiple sources.
        
        Args:
            question: Sub-question to answer
            expected_sources: Suggested source types
            
        Returns:
            SearchResult with retrieved chunks
        """
        chunks: List[RetrievedChunk] = []
        errors: List[str] = []
        
        # Determine which tools to use based on expected sources and question
        tools_to_use = self._select_tools(question, expected_sources)
        
        # Execute tools in parallel for performance
        if tools_to_use:
            # Create parallel tasks for all tools
            tool_tasks = []
            for tool_name in tools_to_use:
                task = self._execute_tool_with_logging(tool_name, question)
                tool_tasks.append(task)
            
            # Run all tools in parallel
            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
            
            # Process results
            for result in tool_results:
                if isinstance(result, Exception):
                    errors.append(f"Tool execution error: {str(result)}")
                elif isinstance(result, list):
                    chunks.extend(result)
        
        # Assess data quality
        quality = self._assess_quality(chunks, errors)
        
        # Identify gaps
        gaps = self._identify_gaps(question, chunks, expected_sources)
        
        return SearchResult(
            sub_question=question,
            retrieved_chunks=chunks,
            search_summary=f"Retrieved {len(chunks)} chunks using {len(tools_to_use)} sources",
            data_quality=quality,
            gaps=gaps,
            retrieval_errors=errors
        )
    
    def _select_tools(self, question: str, expected_sources: List[str]) -> List[str]:
        """Select appropriate tools based on question and expected sources."""
        selected = []
        q_lower = question.lower()
        
        # Map expected sources to tools
        source_tool_map = {
            "nse_data": "nse_stock_data",
            "bse_data": "bse_stock_data",
            "mutual_fund": "mutual_fund_nav",
            "amfi": "mutual_fund_nav",
            "bank_rates": "bank_rates",
            "news": "financial_news",
            "web": "web_search",
            "regulatory": "web_search",
            "rbi": "web_search",
            "sebi": "web_search"
        }
        
        # Add tools based on expected sources
        for source in expected_sources:
            tool_name = source_tool_map.get(source.lower())
            if tool_name and tool_name not in selected:
                selected.append(tool_name)
        
        # Add tools based on question keywords
        if any(term in q_lower for term in ["stock", "share", "nse", "bse"]):
            if "nse_stock_data" not in selected:
                selected.append("nse_stock_data")
        
        if any(term in q_lower for term in ["mutual fund", "nav", "scheme"]):
            if "mutual_fund_nav" not in selected:
                selected.append("mutual_fund_nav")
        
        if any(term in q_lower for term in ["rate", "interest", "loan", "bank"]):
            if "bank_rates" not in selected:
                selected.append("bank_rates")
        
        if any(term in q_lower for term in ["news", "recent", "announcement", "latest"]):
            if "financial_news" not in selected:
                selected.append("financial_news")
        
        # Always include web search as fallback
        if "web_search" not in selected:
            selected.append("web_search")
        
        # Limit to available tools
        selected = [t for t in selected if t in self.tools]
        
        return selected[:4]  # Limit to 4 tools to avoid excessive API calls
    
    async def _execute_tool(self, tool_name: str, question: str) -> List[RetrievedChunk]:
        """
        Execute a specific tool and convert results to RetrievedChunks.
        
        Args:
            tool_name: Name of tool to execute
            question: Query for the tool
            
        Returns:
            List of RetrievedChunk objects
        """
        chunks = []
        
        try:
            tool_func = self.tools[tool_name]
            
            # Execute tool with appropriate parameters
            if tool_name == "web_search":
                results = await tool_func(query=question, max_results=5)
                chunks.extend(self._parse_web_search(results))
                
            elif tool_name in ["nse_stock_data", "bse_stock_data"]:
                # Extract ticker from question
                ticker = self._extract_ticker_from_question(question)
                if ticker:
                    results = await tool_func(symbol=ticker)
                    chunks.extend(self._parse_stock_data(results, tool_name))
                    
            elif tool_name == "mutual_fund_nav":
                fund_name = self._extract_fund_from_question(question)
                if fund_name:
                    results = await tool_func(fund_name=fund_name)
                    chunks.extend(self._parse_nav_data(results))
                    
            elif tool_name == "financial_news":
                results = await tool_func(query=question, max_results=5)
                chunks.extend(self._parse_news(results))
                
            elif tool_name == "bank_rates":
                results = await tool_func(query=question)
                chunks.extend(self._parse_bank_rates(results))
                
        except Exception as exc:
            logger.error(f"Tool {tool_name} execution failed: {exc}")
            raise
        
        return chunks
    
    async def _execute_tool_with_logging(
        self, tool_name: str, question: str
    ) -> List[RetrievedChunk]:
        """
        Execute a tool with logging for parallel execution.
        
        Args:
            tool_name: Name of tool to execute
            question: Query for the tool
            
        Returns:
            List of RetrievedChunk objects or Exception if failed
        """
        logger.debug(f"Executing tool: {tool_name}")
        try:
            return await self._execute_tool(tool_name, question)
        except Exception as exc:
            error_msg = f"{tool_name} failed: {str(exc)}"
            logger.warning(error_msg)
            raise Exception(error_msg)
    
    def _parse_web_search(self, results: Any) -> List[RetrievedChunk]:
        """Parse web search results into chunks."""
        chunks = []
        
        if isinstance(results, list):
            for idx, result in enumerate(results):
                if isinstance(result, dict):
                    chunks.append(RetrievedChunk(
                        content=result.get("snippet", result.get("content", "")),
                        source=result.get("url", result.get("link", f"web_result_{idx}")),
                        source_type="web_search",
                        date=result.get("published_date", datetime.now().strftime("%Y-%m-%d")),
                        relevance_score=result.get("score", 0.7),
                        key_facts=[result.get("title", "")]
                    ))
        
        return chunks
    
    def _parse_stock_data(self, results: Any, source: str) -> List[RetrievedChunk]:
        """Parse stock market data into chunks."""
        chunks = []
        
        if isinstance(results, dict):
            content_parts = []
            key_facts = []
            
            for key, value in results.items():
                if key not in ["_metadata", "_source"]:
                    content_parts.append(f"{key}: {value}")
                    key_facts.append(f"{key}: {value}")
            
            if content_parts:
                chunks.append(RetrievedChunk(
                    content="\n".join(content_parts),
                    source=results.get("_source", source),
                    source_type="exchange_data",
                    date=results.get("date", datetime.now().strftime("%Y-%m-%d")),
                    relevance_score=0.95,
                    key_facts=key_facts
                ))
        
        return chunks
    
    def _parse_nav_data(self, results: Any) -> List[RetrievedChunk]:
        """Parse mutual fund NAV data into chunks."""
        chunks = []
        
        if isinstance(results, dict):
            content = f"Fund: {results.get('fund_name', 'Unknown')}\n"
            content += f"NAV: ₹{results.get('nav', 'N/A')}\n"
            content += f"Date: {results.get('date', 'N/A')}"
            
            chunks.append(RetrievedChunk(
                content=content,
                source="AMFI NAV API",
                source_type="api_data",
                date=results.get("date", datetime.now().strftime("%Y-%m-%d")),
                relevance_score=0.95,
                key_facts=[
                    f"NAV: {results.get('nav')}",
                    f"Fund: {results.get('fund_name')}"
                ]
            ))
        
        return chunks
    
    def _parse_news(self, results: Any) -> List[RetrievedChunk]:
        """Parse financial news into chunks."""
        chunks = []
        
        if isinstance(results, list):
            for article in results:
                if isinstance(article, dict):
                    chunks.append(RetrievedChunk(
                        content=article.get("description", article.get("snippet", "")),
                        source=article.get("url", ""),
                        source_type="news_article",
                        date=article.get("published_date", datetime.now().strftime("%Y-%m-%d")),
                        relevance_score=article.get("relevance", 0.7),
                        key_facts=[article.get("title", "")]
                    ))
        
        return chunks
    
    def _parse_bank_rates(self, results: Any) -> List[RetrievedChunk]:
        """Parse bank rate data into chunks."""
        chunks = []
        
        if isinstance(results, dict):
            for bank, rate_info in results.items():
                if isinstance(rate_info, dict):
                    content = f"{bank}: {rate_info.get('rate', 'N/A')}"
                    chunks.append(RetrievedChunk(
                        content=content,
                        source=rate_info.get("source", "Bank Rate Data"),
                        source_type="rate_data",
                        date=rate_info.get("date", datetime.now().strftime("%Y-%m-%d")),
                        relevance_score=0.9,
                        key_facts=[content]
                    ))
        
        return chunks
    
    def _assess_quality(self, chunks: List[RetrievedChunk], errors: List[str]) -> str:
        """Assess overall data quality of retrieved chunks."""
        if not chunks:
            return "low" if errors else "unknown"
        
        avg_relevance = sum(c.relevance_score for c in chunks) / len(chunks)
        
        # Check source diversity
        source_types = set(c.source_type for c in chunks)
        
        # Check recency (for date-sensitive data)
        recent_count = sum(1 for c in chunks if c.date and self._is_recent(c.date))
        recency_ratio = recent_count / len(chunks) if chunks else 0
        
        # Scoring
        if avg_relevance >= 0.8 and len(source_types) >= 2 and recency_ratio >= 0.7:
            return "high"
        elif avg_relevance >= 0.6 and len(chunks) >= 3:
            return "medium"
        else:
            return "low"
    
    def _is_recent(self, date_str: str) -> bool:
        """Check if date is within last 3 months."""
        try:
            from datetime import datetime, timedelta
            date = datetime.strptime(date_str, "%Y-%m-%d")
            three_months_ago = datetime.now() - timedelta(days=90)
            return date >= three_months_ago
        except:
            return False
    
    def _identify_gaps(
        self, 
        question: str, 
        chunks: List[RetrievedChunk],
        expected_sources: List[str]
    ) -> List[str]:
        """Identify data gaps in retrieved information."""
        gaps = []
        
        if len(chunks) == 0:
            gaps.append("No data retrieved for this sub-question")
            return gaps
        
        # Check if expected sources are missing
        retrieved_types = set(c.source_type for c in chunks)
        
        if "regulatory_filing" in expected_sources and "regulatory_filing" not in retrieved_types:
            gaps.append("Missing regulatory filing data")
        
        if any(s in expected_sources for s in ["api_data", "exchange_data"]) and \
           not any(t in retrieved_types for t in ["api_data", "exchange_data"]):
            gaps.append("Missing official market data")
        
        # Check for low relevance
        low_relevance = [c for c in chunks if c.relevance_score < 0.5]
        if len(low_relevance) > len(chunks) / 2:
            gaps.append("Retrieved data has low relevance to question")
        
        # Check for old data
        old_data = [c for c in chunks if c.date and not self._is_recent(c.date)]
        if old_data and len(old_data) == len(chunks):
            gaps.append("All retrieved data is more than 3 months old")
        
        return gaps
    
    def _extract_ticker_from_question(self, question: str) -> Optional[str]:
        """Extract stock ticker from question."""
        # Reuse logic from lookup agent
        common_tickers = {
            "reliance": "RELIANCE",
            "tcs": "TCS",
            "infosys": "INFY",
            "hdfc bank": "HDFCBANK",
            "icici bank": "ICICIBANK",
            "sbi": "SBIN"
        }
        
        q_lower = question.lower()
        for company, ticker in common_tickers.items():
            if company in q_lower:
                return ticker
        
        import re
        pattern = r'\b([A-Z]{2,10})\b'
        matches = re.findall(pattern, question)
        return matches[0] if matches else None
    
    def _extract_fund_from_question(self, question: str) -> Optional[str]:
        """Extract fund name from question."""
        q_lower = question.lower()
        
        if "axis" in q_lower and "bluechip" in q_lower:
            return "Axis Bluechip Fund"
        elif "hdfc" in q_lower and "top" in q_lower:
            return "HDFC Top 100 Fund"
        
        import re
        pattern = r'(?:fund|scheme)[\s:]+([a-zA-Z\s]+?)(?:\?|$|rate|nav)'
        match = re.search(pattern, q_lower)
        return match.group(1).strip().title() if match else None


# Standalone function for graph integration
async def run_search_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standalone function to run search agent in LangGraph workflow.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state dict with search results
    """
    from app.services.llm import get_llm_client
    
    llm_client = get_llm_client()
    tools = state.get("tools", {})
    
    agent = SearchAgent(llm_client=llm_client, tools=tools)
    result = await agent.run(state)
    
    return {**state, **result}
