#!/usr/bin/env python3
"""
Test script for Marketaux Financial News API integration.

Run this after setting MARKETAUX_API_KEY in .env to verify the integration works.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings
from app.services.news import MarketauxNewsService


async def test_news_service():
    """Test the Marketaux news service."""
    print("🧪 Testing Marketaux Financial News Integration\n")
    print("=" * 60)
    
    # Check if API key is configured
    api_key = getattr(settings, "MARKETAUX_API_KEY", "")
    
    if not api_key:
        print("❌ MARKETAUX_API_KEY not found in environment variables")
        print("\nTo fix this:")
        print("1. Get a free API key from https://www.marketaux.com/register")
        print("2. Add it to backend/.env file:")
        print("   MARKETAUX_API_KEY=your_key_here")
        print("3. Run this test script again")
        return False
    
    print(f"✅ API Key configured: {api_key[:10]}...")
    print()
    
    # Initialize service
    news_service = MarketauxNewsService(api_key)
    
    # Test 1: Get latest news
    print("\n📰 Test 1: Fetching latest financial news (limit=5)")
    print("-" * 60)
    try:
        result = await news_service.get_latest_news(limit=5)
        
        if result.get("success"):
            print(f"✅ Success! Retrieved {result['total']} articles")
            
            # Display first article
            if result['articles']:
                article = result['articles'][0]
                print(f"\nSample Article:")
                print(f"  Title: {article['title']}")
                print(f"  Source: {article['source']}")
                print(f"  Sentiment: {article['sentiment']}")
                print(f"  Entities: {len(article.get('entities', []))} tagged")
                print(f"  URL: {article['url']}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            return False
            
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False
    
    # Test 2: Get trending news
    print("\n\n📈 Test 2: Fetching trending news (last 24 hours)")
    print("-" * 60)
    try:
        result = await news_service.get_trending_news(limit=3, hours=24)
        
        if result.get("success"):
            print(f"✅ Success! Retrieved {result['total']} trending articles")
            print(f"   Timeframe: {result.get('timeframe')}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            
    except Exception as exc:
        print(f"❌ Error: {exc}")
    
    # Test 3: Search news
    print("\n\n🔍 Test 3: Searching for 'Tesla' news")
    print("-" * 60)
    try:
        result = await news_service.search_news(search_term="Tesla", limit=3)
        
        if result.get("success"):
            print(f"✅ Success! Found {result['total']} articles about Tesla")
            
            # Display search results
            for idx, article in enumerate(result['articles'][:2], 1):
                print(f"\n  {idx}. {article['title'][:80]}...")
                print(f"     Sentiment: {article['sentiment']}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            
    except Exception as exc:
        print(f"❌ Error: {exc}")
    
    # Test 4: Filtered news
    print("\n\n🌍 Test 4: Fetching US Technology news")
    print("-" * 60)
    try:
        result = await news_service.get_latest_news(
            limit=3,
            countries="us",
            industries="Technology"
        )
        
        if result.get("success"):
            print(f"✅ Success! Retrieved {result['total']} US tech articles")
            
            # Show metadata
            metadata = result.get('metadata', {})
            filters = metadata.get('filters', {})
            print(f"   Filters applied: {filters}")
        else:
            print(f"❌ Failed: {result.get('error')}")
            
    except Exception as exc:
        print(f"❌ Error: {exc}")
    
    # Close service
    await news_service.close()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("\n💡 Next steps:")
    print("   1. Start the backend: uvicorn app.main:app --reload")
    print("   2. Start the frontend: cd ../frontend && npm run dev")
    print("   3. Click '📰 Financial News' button in the sidebar")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    print("\n" + "🚀 IRIUM Financial News API Test" + "\n")
    
    success = asyncio.run(test_news_service())
    
    sys.exit(0 if success else 1)
