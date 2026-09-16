#!/usr/bin/env python3
"""
Test script to verify that all queries are being routed to simple pipeline.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from app.graph.routing_logic import classify_tier

def test_routing():
    """Test that all queries are routed to simple."""
    test_queries = [
        "What is RBI monetary policy?",  # Would normally be complex
        "Compare HDFC and ICICI loans",  # Would normally be complex
        "Current NAV of Axis Bluechip Fund",  # Would normally be simple
        "Did RBI raise rates last week?",  # Would normally be verify
        "Explain inflation trends in India",  # Would normally be complex
        "What does EBITDA stand for?",  # Would normally be simple
        "Impact of repo rate on borrowers",  # Would normally be complex
    ]
    
    print("🧪 Testing query routing in simple-only mode...\n")
    
    all_simple = True
    
    for query in test_queries:
        tier = classify_tier(query)
        status = "✅" if tier == "simple" else "❌"
        print(f"{status} '{query}' -> {tier}")
        
        if tier != "simple":
            all_simple = False
    
    print(f"\n{'🎉 SUCCESS' if all_simple else '❌ FAILED'}: {'All queries routed to simple' if all_simple else 'Some queries not routed to simple'}")
    return all_simple

if __name__ == "__main__":
    success = test_routing()
    sys.exit(0 if success else 1)