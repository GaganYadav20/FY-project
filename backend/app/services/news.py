"""
Financial News Service using Finnhub API.

Fetches real-time financial news with company-specific and general market news.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FinnhubNewsService:
    """Service for fetching financial news from Finnhub API."""
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self, api_key: str):
        """
        Initialize Finnhub News Service.
        
        Args:
            api_key: Finnhub API key
        """
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def search_news(
        self,
        query: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search for news articles by company symbol or general market news.
        
        Args:
            query: Search query (company symbol like AAPL, TSLA or general keywords)
            limit: Number of articles (Note: Finnhub returns what it has, limit is advisory)
            
        Returns:
            Dictionary with news data and metadata
        """
        try:
            # Try to determine if query is a stock symbol or general keyword
            # Stock symbols are typically 1-5 uppercase letters
            is_symbol = query.strip().isupper() and len(query.strip()) <= 5
            
            if is_symbol:
                # Use company news endpoint
                news_data = await self._get_company_news(query.strip(), limit)
            else:
                # Use general market news endpoint for keywords
                news_data = await self._get_market_news(query, limit)
            
            return news_data
            
        except Exception as exc:
            logger.error(f"Error searching news: {exc}", exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "articles": []
            }
    
    async def _get_company_news(
        self,
        symbol: str,
        limit: int
    ) -> Dict[str, Any]:
        """
        Get company-specific news.
        
        Args:
            symbol: Stock symbol (e.g., AAPL, TSLA)
            limit: Number of articles
            
        Returns:
            Dictionary with company news
        """
        try:
            # Get news from last 30 days
            to_date = datetime.utcnow().strftime("%Y-%m-%d")
            from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            
            params = {
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
                "token": self.api_key
            }
            
            url = f"{self.BASE_URL}/company-news"
            logger.info(f"Fetching company news for {symbol} from Finnhub")
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            articles_raw = response.json()
            
            # Format articles
            articles = []
            for article in articles_raw[:limit]:
                formatted_article = self._format_article(article)
                articles.append(formatted_article)
            
            return {
                "success": True,
                "total": len(articles),
                "articles": articles,
                "metadata": {
                    "fetched_at": datetime.utcnow().isoformat(),
                    "source": "Finnhub API",
                    "query_type": "company",
                    "symbol": symbol
                }
            }
            
        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP error fetching company news: {exc.response.status_code}")
            return {
                "success": False,
                "error": f"API error: {exc.response.status_code}",
                "articles": []
            }
        except Exception as exc:
            logger.error(f"Error fetching company news: {exc}", exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "articles": []
            }
    
    async def _get_market_news(
        self,
        query: str,
        limit: int,
        category: str = "general"
    ) -> Dict[str, Any]:
        """
        Get general market news.
        
        Args:
            query: Search keywords
            limit: Number of articles
            category: News category (general, forex, crypto, merger)
            
        Returns:
            Dictionary with market news
        """
        try:
            # Determine category from query keywords
            q_lower = query.lower()
            if any(word in q_lower for word in ["crypto", "bitcoin", "ethereum", "cryptocurrency"]):
                category = "crypto"
            elif any(word in q_lower for word in ["forex", "currency", "exchange rate", "dollar", "euro"]):
                category = "forex"
            elif any(word in q_lower for word in ["merger", "acquisition", "m&a", "takeover"]):
                category = "merger"
            
            params = {
                "category": category,
                "token": self.api_key
            }
            
            url = f"{self.BASE_URL}/news"
            logger.info(f"Fetching market news (category: {category}) from Finnhub")
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            articles_raw = response.json()
            
            # Filter articles by query keywords if provided
            filtered_articles = []
            if query and category == "general":
                query_terms = query.lower().split()
                for article in articles_raw:
                    article_text = f"{article.get('headline', '')} {article.get('summary', '')}".lower()
                    if any(term in article_text for term in query_terms):
                        filtered_articles.append(article)
            else:
                filtered_articles = articles_raw
            
            # Format articles
            articles = []
            for article in filtered_articles[:limit]:
                formatted_article = self._format_article(article)
                articles.append(formatted_article)
            
            return {
                "success": True,
                "total": len(articles),
                "articles": articles,
                "metadata": {
                    "fetched_at": datetime.utcnow().isoformat(),
                    "source": "Finnhub API",
                    "query_type": "market",
                    "category": category,
                    "search_query": query
                }
            }
            
        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP error fetching market news: {exc.response.status_code}")
            return {
                "success": False,
                "error": f"API error: {exc.response.status_code}",
                "articles": []
            }
        except Exception as exc:
            logger.error(f"Error fetching market news: {exc}", exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "articles": []
            }
    
    def _format_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single news article for consistent output."""
        # Finnhub uses different field names
        return {
            "id": article.get("id", article.get("datetime", "")),
            "title": article.get("headline", ""),
            "description": article.get("summary", ""),
            "url": article.get("url", ""),
            "image_url": article.get("image", ""),
            "published_at": datetime.fromtimestamp(article.get("datetime", 0)).isoformat() if article.get("datetime") else "",
            "source": article.get("source", "Finnhub"),
            "category": article.get("category", "general"),
            "related_symbols": article.get("related", "").split(",") if article.get("related") else []
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global service instance
_news_service_instance = None


def get_news_service(api_key: str = None) -> FinnhubNewsService:
    """Get or create news service instance."""
    global _news_service_instance
    
    if api_key and (_news_service_instance is None or _news_service_instance.api_key != api_key):
        _news_service_instance = FinnhubNewsService(api_key)
    
    return _news_service_instance
