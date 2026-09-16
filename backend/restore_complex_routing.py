#!/usr/bin/env python3
"""
Script to restore normal (complex) routing logic.

Run this script to revert the temporary simple-only routing back to the original 
complex routing logic that uses the full multi-agent pipeline.
"""

import os
import sys

def restore_complex_routing():
    """Restore the original complex routing logic."""
    routing_file = "app/graph/routing_logic.py"
    
    if not os.path.exists(routing_file):
        print(f"Error: {routing_file} not found!")
        return False
    
    # Read the current file
    with open(routing_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we're in temporary mode
    if "# TEMPORARY: Force all queries to simple pipeline" not in content:
        print("System is not in temporary simple mode. No changes needed.")
        return True
    
    # Replace the temporary function with the original logic
    temp_function = '''def classify_tier(query: str) -> str:
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
    #     return _keyword_fallback_classify(query)'''

    original_function = '''def classify_tier(query: str) -> str:
    """
    Classify query tier using keyword rules and LLM fallback.
    
    Args:
        query: User query
        
    Returns:
        Tier: "simple", "verify", "complex", or "unclear"
    """
    q = query.lower().strip()
    
    # Handle empty or very short unclear queries
    if len(q) < 3 or any(pattern == q for pattern in UNCLEAR_QUERIES):
        return "unclear"
    
    # Check if query is asking to repeat/retry without context
    if q in ["try again", "again", "retry", "do it again"]:
        return "unclear"

    # 0. Pure abbreviation / "stands for" queries are ALWAYS simple — one-line answer.
    abbreviation_patterns = [
        "what does ", "what do ", "full form of ", "abbreviation of ",
        "stand for", "stands for", "expand "
    ]
    if any(pat in q for pat in abbreviation_patterns):
        # Only treat as simple if it's truly asking for an expansion, not context
        context_words = ["policy", "stance", "explain", "why", "how", "impact", "effect"]
        if not any(cw in q for cw in context_words):
            return "simple"

    # 1. Complex indicators take highest priority — policy/analysis topics always
    #    go through the full research pipeline regardless of query length.
    if any(k in q for k in COMPLEX_KEYWORDS):
        return "complex"

    # 2. Verify patterns — recent event fact-checks
    if any(k in q for k in VERIFY_KEYWORDS):
        return "verify"

    # 3. Simple patterns — pure single-fact lookups (price, NAV, term definition)
    if any(k in q for k in SIMPLE_KEYWORDS):
        # Extra guard: if the query is asking about a *policy*, *outlook*, or
        # *implication*, escalate to complex even if a simple keyword matched.
        escalation_words = [
            "policy", "outlook", "stance", "forecast", "implication",
            "rbi", "mpc", "sebi", "fed", "inflation", "gdp", "repo"
        ]
        if any(ew in q for ew in escalation_words):
            return "complex"
        return "simple"

    # 4. Fallback: LLM classification with error handling
    try:
        return _llm_classify(query)
    except Exception as exc:
        logger.warning(f"LLM classification failed: {exc}, using keyword fallback")
        return _keyword_fallback_classify(query)'''

    # Replace the function in the content
    new_content = content.replace(temp_function, original_function)
    
    # Write back to file
    with open(routing_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Complex routing logic restored successfully!")
    print("All queries will now use the full multi-agent pipeline based on tier classification.")
    return True

if __name__ == "__main__":
    print("🔄 Restoring complex routing logic...")
    success = restore_complex_routing()
    sys.exit(0 if success else 1)