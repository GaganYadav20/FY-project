"""
Visualization Service for creating charts and structured data responses.

Generates chart data and structured information for financial queries.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VisualizationService:
    """Service for creating charts and structured data visualizations."""
    
    @staticmethod
    def create_stock_chart(stock_data: Dict[str, Any], historical_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Create stock price chart data.
        
        Args:
            stock_data: Current stock information
            historical_data: Historical price data (optional)
            
        Returns:
            Chart data structure
        """
        try:
            symbol = stock_data.get("symbol", "Unknown")
            current_price = stock_data.get("price", 0)
            change = stock_data.get("change", 0)
            change_percent = stock_data.get("change_percent", 0)
            
            # Basic price chart (gauge/indicator style)
            chart_data = {
                "type": "line",
                "title": f"{symbol} Stock Price Trend",
                "data": {
                    "labels": [],
                    "datasets": [{
                        "label": f"{symbol} Price (₹)",
                        "data": [],
                        "borderColor": "rgb(34, 197, 94)" if change >= 0 else "rgb(239, 68, 68)",
                        "backgroundColor": "rgba(34, 197, 94, 0.1)" if change >= 0 else "rgba(239, 68, 68, 0.1)",
                        "tension": 0.4
                    }]
                },
                "config": {
                    "responsive": True,
                    "plugins": {
                        "legend": {"display": True},
                        "title": {"display": True, "text": f"{symbol} Price Movement"}
                    },
                    "scales": {
                        "y": {
                            "beginAtZero": False,
                            "title": {"display": True, "text": "Price (₹)"}
                        }
                    }
                }
            }
            
            if historical_data and len(historical_data) > 0:
                # Use historical data
                chart_data["data"]["labels"] = [item.get("date", "") for item in historical_data[-30:]]  # Last 30 days
                chart_data["data"]["datasets"][0]["data"] = [item.get("close", 0) for item in historical_data[-30:]]
            else:
                # Generate simple trend data (mock for demonstration)
                base_price = current_price - change
                dates = []
                prices = []
                
                for i in range(7):  # Last 7 days trend
                    date = (datetime.now() - timedelta(days=6-i)).strftime("%m/%d")
                    dates.append(date)
                    
                    if i == 6:  # Today
                        prices.append(current_price)
                    else:
                        # Generate realistic price movement
                        variation = (i - 3) * (change / 3) if change != 0 else 0
                        prices.append(base_price + variation)
                
                chart_data["data"]["labels"] = dates
                chart_data["data"]["datasets"][0]["data"] = prices
            
            return chart_data
            
        except Exception as exc:
            logger.error(f"Failed to create stock chart: {exc}")
            return {}
    
    @staticmethod
    def create_stock_metrics_table(stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create structured stock metrics table.
        
        Args:
            stock_data: Stock information
            
        Returns:
            Structured data for metrics table
        """
        try:
            metrics = {
                "type": "stock_metrics",
                "title": f"{stock_data.get('symbol', 'Stock')} Key Metrics",
                "data": {
                    "rows": [
                        {"metric": "Current Price", "value": f"₹{stock_data.get('price', 0):.2f}"},
                        {"metric": "Change", "value": f"₹{stock_data.get('change', 0):.2f}"},
                        {"metric": "Change %", "value": f"{stock_data.get('change_percent', 0):.2f}%"},
                        {"metric": "Volume", "value": f"{stock_data.get('volume', 0):,}"},
                        {"metric": "Market Cap", "value": VisualizationService._format_large_number(stock_data.get('market_cap'))},
                        {"metric": "P/E Ratio", "value": f"{stock_data.get('pe_ratio', 'N/A')}"},
                        {"metric": "Data Source", "value": stock_data.get('_source', 'Market Data')},
                        {"metric": "Last Updated", "value": stock_data.get('date', datetime.now().strftime("%Y-%m-%d"))}
                    ],
                    "columns": ["metric", "value"]
                }
            }
            
            return metrics
            
        except Exception as exc:
            logger.error(f"Failed to create stock metrics: {exc}")
            return {}
    
    @staticmethod
    def create_mutual_fund_chart(nav_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create mutual fund NAV chart.
        
        Args:
            nav_data: NAV information
            
        Returns:
            Chart data structure
        """
        try:
            fund_name = nav_data.get("fund_name", "Mutual Fund")
            nav_value = nav_data.get("nav", 0)
            
            # Simple NAV indicator chart
            chart_data = {
                "type": "bar",
                "title": f"{fund_name} - Current NAV",
                "data": {
                    "labels": ["Current NAV"],
                    "datasets": [{
                        "label": "NAV Value (₹)",
                        "data": [nav_value],
                        "backgroundColor": "rgba(59, 130, 246, 0.8)",
                        "borderColor": "rgb(59, 130, 246)",
                        "borderWidth": 1
                    }]
                },
                "config": {
                    "responsive": True,
                    "plugins": {
                        "legend": {"display": True},
                        "title": {"display": True, "text": f"{fund_name} NAV"}
                    },
                    "scales": {
                        "y": {
                            "beginAtZero": True,
                            "title": {"display": True, "text": "NAV (₹)"}
                        }
                    }
                }
            }
            
            return chart_data
            
        except Exception as exc:
            logger.error(f"Failed to create mutual fund chart: {exc}")
            return {}
    
    @staticmethod
    def create_interest_rates_chart(rates_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create interest rates comparison chart.
        
        Args:
            rates_data: Bank rates information
            
        Returns:
            Chart data structure
        """
        try:
            banks = list(rates_data.keys())[:5]  # Top 5 banks
            
            chart_data = {
                "type": "bar",
                "title": "Bank Interest Rates Comparison",
                "data": {
                    "labels": banks,
                    "datasets": [{
                        "label": "Interest Rate (%)",
                        "data": [7.5, 8.0, 7.8, 7.3, 7.9],  # Sample rates
                        "backgroundColor": [
                            "rgba(255, 99, 132, 0.8)",
                            "rgba(54, 162, 235, 0.8)", 
                            "rgba(255, 205, 86, 0.8)",
                            "rgba(75, 192, 192, 0.8)",
                            "rgba(153, 102, 255, 0.8)"
                        ],
                        "borderWidth": 1
                    }]
                },
                "config": {
                    "responsive": True,
                    "plugins": {
                        "legend": {"display": True},
                        "title": {"display": True, "text": "Current Interest Rates by Bank"}
                    },
                    "scales": {
                        "y": {
                            "beginAtZero": True,
                            "title": {"display": True, "text": "Interest Rate (%)"}
                        }
                    }
                }
            }
            
            return chart_data
            
        except Exception as exc:
            logger.error(f"Failed to create rates chart: {exc}")
            return {}
    
    @staticmethod
    def _format_large_number(number):
        """Format large numbers in a readable format."""
        if number is None or number == 0:
            return "N/A"
        
        try:
            num = float(number)
            if num >= 1_00_000_00_000:  # 1000 Crores
                return f"₹{num/1_00_000_00_000:.1f}K Cr"
            elif num >= 1_00_000_000:  # 1 Crore
                return f"₹{num/1_00_000_000:.1f} Cr"
            elif num >= 1_00_000:  # 1 Lakh
                return f"₹{num/1_00_000:.1f} L"
            else:
                return f"₹{num:,.0f}"
        except:
            return str(number)
    
    @staticmethod
    def enhance_response_with_visuals(
        query: str, 
        response_text: str, 
        tool_results: List[Dict] = None
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Enhance a response with relevant charts and structured data.
        
        Args:
            query: Original query
            response_text: Text response
            tool_results: Results from tool executions
            
        Returns:
            Tuple of (charts, structured_data, metadata)
        """
        charts = []
        structured_data = []
        metadata = {}
        
        if not tool_results:
            return charts, structured_data, metadata
        
        try:
            q_lower = query.lower()
            
            for tool_result in tool_results:
                tool_name = tool_result.get("tool", "")
                result_data = tool_result.get("result", {})
                
                if tool_name == "nse_stock_data" and result_data:
                    # Add stock chart
                    chart = VisualizationService.create_stock_chart(result_data)
                    if chart:
                        charts.append(chart)
                    
                    # Add metrics table
                    metrics = VisualizationService.create_stock_metrics_table(result_data)
                    if metrics:
                        structured_data.append(metrics)
                        
                    metadata["stock_symbol"] = result_data.get("symbol")
                    metadata["data_source"] = result_data.get("_source")
                
                elif tool_name == "mutual_fund_nav" and result_data:
                    # Add NAV chart
                    chart = VisualizationService.create_mutual_fund_chart(result_data)
                    if chart:
                        charts.append(chart)
                    
                    # Add fund info table
                    fund_info = {
                        "type": "fund_info",
                        "title": "Fund Information",
                        "data": {
                            "rows": [
                                {"metric": "Fund Name", "value": result_data.get("fund_name", "N/A")},
                                {"metric": "NAV", "value": f"₹{result_data.get('nav', 0):.4f}"},
                                {"metric": "Date", "value": result_data.get("date", "N/A")},
                                {"metric": "Fund House", "value": result_data.get("fund_house", "N/A")},
                                {"metric": "Category", "value": result_data.get("category", "N/A")}
                            ],
                            "columns": ["metric", "value"]
                        }
                    }
                    structured_data.append(fund_info)
                
                elif tool_name == "bank_rates" and result_data:
                    # Add rates chart
                    chart = VisualizationService.create_interest_rates_chart(result_data)
                    if chart:
                        charts.append(chart)
            
            # Set metadata
            metadata["has_visuals"] = len(charts) > 0 or len(structured_data) > 0
            metadata["chart_count"] = len(charts)
            metadata["data_table_count"] = len(structured_data)
            
        except Exception as exc:
            logger.error(f"Failed to enhance response with visuals: {exc}")
        
        return charts, structured_data, metadata


# Global service instance
_visualization_service = VisualizationService()


def get_visualization_service() -> VisualizationService:
    """Get the visualization service instance."""
    return _visualization_service