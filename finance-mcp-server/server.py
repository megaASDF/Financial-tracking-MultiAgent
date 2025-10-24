"""
Finance MCP Server
Provides stock market data, company info, and financial news tools
"""

from fastmcp import FastMCP
import httpx
from datetime import datetime, timedelta

# Initialize FastMCP server
mcp = FastMCP("finance-server")

# You'll need API keys - get free ones from:
# Alpha Vantage: https://www.alphavantage.co/support/#api-key
# NewsAPI: https://newsapi.org/register

ALPHA_VANTAGE_API_KEY ="G96FOP6NZOOXV1KO"  # Replace with your key


@mcp.tool()
async def get_stock_price(symbol: str) -> dict:
    """
    Get current stock price and basic info for a given ticker symbol.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'MSFT')
    
    Returns:
        Dictionary with current price, change, and volume
    """
    try:
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol.upper(),
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
        
        if "Global Quote" not in data or not data["Global Quote"]:
            return {
                "error": f"Stock symbol '{symbol}' not found or API limit reached",
                "tip": "Try again in a minute or check if the symbol is correct"
            }
        
        quote = data["Global Quote"]
        return {
            "symbol": quote.get("01. symbol", symbol),
            "price": quote.get("05. price", "N/A"),
            "change": quote.get("09. change", "N/A"),
            "change_percent": quote.get("10. change percent", "N/A"),
            "volume": quote.get("06. volume", "N/A"),
            "last_updated": quote.get("07. latest trading day", "N/A")
        }
    
    except Exception as e:
        return {"error": f"Failed to fetch stock price: {str(e)}"}


@mcp.tool()
async def get_company_overview(symbol: str) -> dict:
    """
    Get detailed company information including sector, market cap, and financial metrics.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
    
    Returns:
        Dictionary with company overview data
    """
    try:
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": "OVERVIEW",
            "symbol": symbol.upper(),
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
        
        if not data or "Symbol" not in data:
            return {
                "error": f"Company data for '{symbol}' not found",
                "tip": "Check if the ticker symbol is correct"
            }
        
        return {
            "symbol": data.get("Symbol", symbol),
            "name": data.get("Name", "N/A"),
            "description": data.get("Description", "N/A")[:500] + "...",
            "sector": data.get("Sector", "N/A"),
            "industry": data.get("Industry", "N/A"),
            "market_cap": data.get("MarketCapitalization", "N/A"),
            "pe_ratio": data.get("PERatio", "N/A"),
            "dividend_yield": data.get("DividendYield", "N/A"),
            "52_week_high": data.get("52WeekHigh", "N/A"),
            "52_week_low": data.get("52WeekLow", "N/A")
        }
    
    except Exception as e:
        return {"error": f"Failed to fetch company overview: {str(e)}"}


@mcp.tool()
async def get_financial_statements(symbol: str, statement_type: str = "income") -> dict:
    """
    Get financial statements (income statement, balance sheet, or cash flow).
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        statement_type: Type of statement - 'income', 'balance', or 'cashflow'
    
    Returns:
        Dictionary with annual financial data
    """
    try:
        function_map = {
            "income": "INCOME_STATEMENT",
            "balance": "BALANCE_SHEET",
            "cashflow": "CASH_FLOW"
        }
        
        function = function_map.get(statement_type.lower(), "INCOME_STATEMENT")
        
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": function,
            "symbol": symbol.upper(),
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
        
        if "annualReports" not in data or not data["annualReports"]:
            return {
                "error": f"Financial statements for '{symbol}' not available",
                "tip": "Try a different stock or check back later"
            }
        
        # Get the most recent annual report
        latest = data["annualReports"][0]
        
        return {
            "symbol": data.get("symbol", symbol),
            "statement_type": statement_type,
            "fiscal_date": latest.get("fiscalDateEnding", "N/A"),
            "data": latest
        }
    
    except Exception as e:
        return {"error": f"Failed to fetch financial statements: {str(e)}"}


@mcp.tool()
async def get_market_news(query: str = "stock market", limit: int = 5) -> dict:
    """
    Get latest financial and market news articles.
    
    Args:
        query: Search query for news (e.g., 'Apple stock', 'tech stocks')
        limit: Number of articles to return (1-10)
    
    Returns:
        Dictionary with news articles
    """
    try:
        limit = min(max(1, limit), 10)  # Ensure limit is between 1-10
        
        # Calculate date 7 days ago for recent news
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": limit,
            "apiKey": NEWS_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
        
        if data.get("status") != "ok":
            return {
                "error": "Failed to fetch news",
                "message": data.get("message", "Unknown error")
            }
        
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article.get("title", "N/A"),
                "description": article.get("description", "N/A"),
                "source": article.get("source", {}).get("name", "N/A"),
                "published_at": article.get("publishedAt", "N/A"),
                "url": article.get("url", "N/A")
            })
        
        return {
            "query": query,
            "total_results": data.get("totalResults", 0),
            "articles": articles
        }
    
    except Exception as e:
        return {"error": f"Failed to fetch news: {str(e)}"}


@mcp.tool()
async def search_stocks(keywords: str) -> dict:
    """
    Search for stocks by company name or keywords.
    
    Args:
        keywords: Company name or keywords to search (e.g., 'Apple', 'Tesla')
    
    Returns:
        List of matching stocks with symbols
    """
    try:
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": "SYMBOL_SEARCH",
            "keywords": keywords,
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
        
        if "bestMatches" not in data:
            return {
                "error": "No matches found",
                "tip": "Try different keywords or check spelling"
            }
        
        results = []
        for match in data["bestMatches"][:5]:  # Top 5 results
            results.append({
                "symbol": match.get("1. symbol", "N/A"),
                "name": match.get("2. name", "N/A"),
                "type": match.get("3. type", "N/A"),
                "region": match.get("4. region", "N/A"),
                "currency": match.get("8. currency", "N/A")
            })
        
        return {
            "query": keywords,
            "matches": results
        }
    
    except Exception as e:
        return {"error": f"Failed to search stocks: {str(e)}"}


if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="stdio")