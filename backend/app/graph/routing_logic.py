# backend/app/graph/routing_logic.py
"""
Enhanced Query Router with improved classification logic.

Classifies queries into: simple (lookup), verify (fact-check), complex (research).
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Keyword patterns for each tier

# SIMPLE: Only pure single-fact lookups — a single number, definition, or price.
# DO NOT add broad patterns like "what is" here (they swallow policy/outlook queries).
SIMPLE_KEYWORDS = [
    "current nav", "nav of",
    "current price", "stock price", "rate today",
    "home loan rate", "fd rate", "exchange rate",
    "define", "meaning of", "explain briefly",
    "what does", "full form of", "abbreviation"
]

# VERIFY: Recent event fact-checks
VERIFY_KEYWORDS = [
    "days ago", "last week", "this week", "recently",
    "did", "has", "announced", "happened", "merged",
    "new circular", "rate change", "verify",
    "is it true", "confirm", "check if"
]

# COMPLEX: Analysis, research, policies, outlooks, and multi-part explanations
COMPLEX_KEYWORDS = [
    "compare", "comparison", "vs", "versus", "difference", "diff", "between",
    "analysis", "research", "critical assessment",
    "report", "explain in detail", "difference between", "impact of",
    "trend", "history", "overview", "study", "portfolio",
    "research paper", "write", "detailed analysis", "comprehensive",
    # Policy and macro-economic topics that always need full research pipeline
    "policy", "monetary policy", "fiscal policy", "rbi policy", "fed policy",
    "rbi", "reserve bank", "interest rate policy", "rate decision", "mpc",
    "monetary policy committee", "repo rate", "inflation", "gdp",
    "economic outlook", "growth forecast", "growth projection",
    "what is rbi", "what is the rbi", "what is the fed",
    "stance", "neutral stance", "hawkish", "dovish",
    "implications", "borrowers", "savers", "cpi", "wpi",
    "budget", "fiscal deficit", "trade deficit", "current account",
    "sebi", "market regulator", "banking sector", "npa"
]

# Ambiguous/unclear queries that need clarification
UNCLEAR_QUERIES = [
    "try again", "again", "retry", "do it again", "one more time",
    "what", "huh", "?", "...", "repeat", "say that again"
]


def classify_tier(query: str) -> str:
    """
    Classify query tier using keyword rules and LLM fallback.
    
    Args:
        query: User query
        
    Returns:
        Tier: "simple", "verify", "complex", or "unclear"
    """
    # TEMPORARY: Force all queries to simple pipeline
    # This bypasses the complex multi-agent pipeline temporarily
    logger.info(f"TEMPORARY MODE: Routing all queries to simple pipeline for query: {query}")
    
    q = query.lower().strip()
    
    # Handle empty or very short unclear queries
    if len(q) < 3 or any(pattern == q for pattern in UNCLEAR_QUERIES):
        return "unclear"
    
    # Check if query is asking to repeat/retry without context
    if q in ["try again", "again", "retry", "do it again"]:
        return "unclear"

    # TEMPORARY: Return simple for all non-unclear queries
    return "simple"

    # ORIGINAL CODE BELOW - COMMENTED OUT FOR TEMPORARY SIMPLE MODE
    # Uncomment this section and remove the "return simple" above to restore normal routing
    
    # # 0. Pure abbreviation / "stands for" queries are ALWAYS simple — one-line answer.
    # abbreviation_patterns = [
    #     "what does ", "what do ", "full form of ", "abbreviation of ",
    #     "stand for", "stands for", "expand "
    # ]
    # if any(pat in q for pat in abbreviation_patterns):
    #     # Only treat as simple if it's truly asking for an expansion, not context
    #     context_words = ["policy", "stance", "explain", "why", "how", "impact", "effect"]
    #     if not any(cw in q for cw in context_words):
    #         return "simple"

    # # 1. Complex indicators take highest priority — policy/analysis topics always
    # #    go through the full research pipeline regardless of query length.
    # if any(k in q for k in COMPLEX_KEYWORDS):
    #     return "complex"

    # # 2. Verify patterns — recent event fact-checks
    # if any(k in q for k in VERIFY_KEYWORDS):
    #     return "verify"

    # # 3. Simple patterns — pure single-fact lookups (price, NAV, term definition)
    # if any(k in q for k in SIMPLE_KEYWORDS):
    #     # Extra guard: if the query is asking about a *policy*, *outlook*, or
    #     # *implication*, escalate to complex even if a simple keyword matched.
    #     escalation_words = [
    #         "policy", "outlook", "stance", "forecast", "implication",
    #         "rbi", "mpc", "sebi", "fed", "inflation", "gdp", "repo"
    #     ]
    #     if any(ew in q for ew in escalation_words):
    #         return "complex"
    #     return "simple"

    # # 4. Fallback: LLM classification with error handling
    # try:
    #     return _llm_classify(query)
    # except Exception as exc:
    #     logger.warning(f"LLM classification failed: {exc}, using keyword fallback")
    #     return _keyword_fallback_classify(query)


def _llm_classify(query: str) -> str:
    """Use LLM to classify query tier with timeout handling."""
    try:
        from app.services.llm import get_llm_client
        import asyncio
        
        llm = get_llm_client()
        
        prompt = f"""Classify this financial query into exactly one category:

Categories:
- simple: A pure single-fact lookup needing ONE specific number, price, or one-line definition.
  Examples:
    "NAV of Axis Bluechip Fund?" → simple (single number)
    "What does EBITDA stand for?" → simple (one-line definition)
    "HDFC Bank stock price?" → simple (single price)
  NOT simple: "What is the RBI monetary policy?" → needs rates + outlook + rationale + implications → complex
  NOT simple: "What is the repo rate in 2026?" → needs policy context, not just a number → complex

- verify: Verify whether a specific recent event, announcement, or claim is true.
  Examples: "Did RBI raise rates last week?", "Has HDFC merged with ICICI?"

- complex: Requires research, web search, multiple data points, analysis, comparison, policy context, or structured explanation.
  Examples:
    "What is RBI policy in 2026?" → complex (rates + stance + inflation + GDP + implications)
    "Compare HDFC and ICICI home loans" → complex
    "Explain India's monetary policy stance" → complex
    "Impact of RBI rate cut on borrowers" → complex
    "Banking sector NPA trends" → complex

Rule: When in doubt between simple and complex, choose complex.

Query: "{query}"

Reply with ONLY one word: simple, verify, or complex"""

        # Use sync invoke with error handling for 504 timeouts
        try:
            response = llm.invoke(prompt)
            
            if hasattr(response, 'content'):
                result = response.content.strip().lower()
            else:
                result = str(response).strip().lower()
            
            # Validate result
            if result in ["simple", "verify", "complex"]:
                logger.info(f"LLM classified query as: {result}")
                return result
            else:
                logger.warning(f"LLM returned invalid classification: {result}, defaulting to complex")
                return "complex"
        
        except Exception as llm_exc:
            # Check for specific timeout/gateway errors
            error_msg = str(llm_exc)
            if "504" in error_msg or "timeout" in error_msg.lower():
                logger.warning(f"LLM classification timed out (504), using fallback classification")
                return _keyword_fallback_classify(query)
            elif "502" in error_msg or "503" in error_msg:
                logger.warning(f"LLM service unavailable, using fallback classification")
                return _keyword_fallback_classify(query)
            else:
                logger.warning(f"LLM classification failed: {llm_exc}, using fallback")
                return _keyword_fallback_classify(query)
    
    except Exception as exc:
        logger.error(f"LLM classification error: {exc}")
        return _keyword_fallback_classify(query)


def _keyword_fallback_classify(query: str) -> str:
    """
    Fallback classification using only keywords when LLM fails.
    More conservative - defaults to complex for ambiguous cases.
    """
    q = query.lower().strip()
    
    # Be more strict about simple classification when LLM is unavailable
    strict_simple_patterns = [
        "current nav of", "nav of", "what is the nav",
        "current price of", "stock price of", "share price",
        "define", "what does", "stands for", "full form",
        "exchange rate", "fd rate", "current rate"
    ]
    
    # Only classify as simple if it clearly matches a single-fact lookup pattern
    if any(pattern in q for pattern in strict_simple_patterns):
        # Extra safety: check for complex indicators
        complex_indicators = ["compare", "analysis", "policy", "why", "how", "impact", "difference"]
        if not any(indicator in q for indicator in complex_indicators):
            return "simple"
    
    # Default to complex when in doubt (safer for user experience)
    logger.info(f"Fallback classification: defaulting to complex for query: {query}")
    return "complex"


def router_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Router agent that classifies query tier.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with tier classification
    """
    query = state.get("query_text") or state.get("raw_query", "")
    
    logger.info(f"Router classifying query: {query}")
    
    tier = classify_tier(query)
    
    logger.info(f"Query classified as tier: {tier}")
    
    return {
        **state,
        "tier": tier,
        "current_stage": "routing_complete"
    }


def should_use_lookup(query: str) -> bool:
    """
    Quick check if query should use simple lookup path.
    
    Args:
        query: User query
        
    Returns:
        True if should use lookup, False otherwise
    """
    tier = classify_tier(query)
    return tier == "simple"


def should_use_full_pipeline(query: str) -> bool:
    """
    Quick check if query needs full research pipeline.
    
    Args:
        query: User query
        
    Returns:
        True if needs full pipeline, False otherwise
    """
    tier = classify_tier(query)
    return tier in ["verify", "complex"]