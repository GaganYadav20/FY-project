"""
Quick test script to verify query processing works with multi-agent workflow.
"""

import asyncio
import logging
from app.config import settings
from app.graph.tools import initialize_tools
from app.graph.graph import execute_research_workflow

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_query(query: str):
    """Test a query through the workflow."""
    print("\n" + "="*70)
    print(f"TESTING QUERY: {query}")
    print("="*70)
    
    # Check configuration
    print(f"\n✓ GROQ_API_KEY configured: {bool(settings.GROQ_API_KEY)}")
    print(f"✓ TAVILY_API_KEY configured: {bool(settings.TAVILY_API_KEY)}")
    print(f"✓ MARKETAUX_API_KEY configured: {bool(settings.MARKETAUX_API_KEY)}")
    print(f"✓ API_NINJAS_KEY configured: {bool(settings.API_NINJAS_KEY)}")
    
    # Prepare tool config
    tool_config = {
        "GROQ_API_KEY": settings.GROQ_API_KEY,
        "TAVILY_API_KEY": settings.TAVILY_API_KEY,
        "MARKETAUX_API_KEY": settings.MARKETAUX_API_KEY,
        "API_NINJAS_KEY": settings.API_NINJAS_KEY,
        "MODEL_NAME": settings.MODEL_NAME,
        "LLM_TEMPERATURE": settings.LLM_TEMPERATURE
    }
    
    # Initialize tools
    print("\n📦 Initializing tools...")
    tools = initialize_tools(tool_config)
    print(f"✓ Tools initialized: {list(tools.keys())}")
    
    # Execute workflow
    print(f"\n🚀 Executing workflow...")
    try:
        final_state = await execute_research_workflow(
            query=query,
            domain="fintech",
            tools=tools,
            user_id="test_user",
            session_id="test_session"
        )
        
        print(f"\n✅ Workflow completed!")
        print(f"   Tier: {final_state.get('tier')}")
        print(f"   Stage: {final_state.get('current_stage')}")
        print(f"   Errors: {final_state.get('errors', [])}")
        
        answer = final_state.get("final_answer", "No answer")
        print(f"\n📋 ANSWER:")
        print("-"*70)
        print(answer)
        print("-"*70)
        
        return final_state
        
    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run tests."""
    # Test 1: Simple query
    await test_query("what is ebitda")
    
    # Test 2: Stock query
    # await test_query("what is the current price of Reliance stock")
    
    # Test 3: Complex query
    # await test_query("analyze the impact of RBI interest rate changes on banking stocks")


if __name__ == "__main__":
    asyncio.run(main())
