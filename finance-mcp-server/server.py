"""
Finance MCP Server - Yahoo Finance + VNDirect Edition
Provides comprehensive stock data for US & Vietnamese markets
- Uses Yahoo Finance for US stocks (no rate limits!)
- Uses VNDirect for Vietnamese stocks
- Full historical data support
"""

from fastmcp import FastMCP
import httpx
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Initialize FastMCP server
mcp = FastMCP("finance-server")

# Create executor for running sync yfinance code
executor = ThreadPoolExecutor(max_workers=3)

# Import yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("Warning: yfinance not installed. US stock features will be limited.")

NEWS_API_KEY = "your_newsapi_key"


def is_vietnamese_stock(symbol: str) -> bool:
    """Check if symbol is Vietnamese (typically 3 letters without .VN suffix)"""
    clean_symbol = symbol.replace('.VN', '')
    return len(clean_symbol) <= 3 and clean_symbol.isalpha()


@mcp.tool()
async def get_stock_price(symbol: str) -> dict:
    """
    Get current stock price for US or Vietnamese stocks.
    
    Args:
        symbol: Stock ticker (US: 'AAPL', 'GOOGL' | VN: 'VNM', 'VCB', 'FPT')
    
    Returns:
        Dictionary with current price, change, and volume
    """
    symbol = symbol.upper()
    
    try:
        if is_vietnamese_stock(symbol):
            # Add .VN suffix for Yahoo Finance
            yf_symbol = f"{symbol}.VN"
            
            def get_yf_data():
                ticker = yf.Ticker(yf_symbol)
                info = ticker.info
                hist = ticker.history(period="2d")
                return info, hist
            
            loop = asyncio.get_event_loop()
            info, hist = await loop.run_in_executor(executor, get_yf_data)
            
            if hist.empty:
                return {"error": f"No data for Vietnamese stock '{symbol}'"}
            
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            
            change = latest['Close'] - prev['Close']
            change_pct = (change / prev['Close'] * 100) if prev['Close'] != 0 else 0
            
            return {
                "symbol": symbol,
                "exchange": "Vietnam (HOSE/HNX)",
                "price": f"{latest['Close']:,.0f} VND",
                "change": f"{change:,.0f} VND",
                "change_percent": f"{change_pct:.2f}%",
                "volume": f"{int(latest['Volume']):,}",
                "high": f"{latest['High']:,.0f} VND",
                "low": f"{latest['Low']:,.0f} VND",
                "market_cap": f"{info.get('marketCap', 0):,.0f} VND" if info.get('marketCap') else "N/A",
                "last_updated": latest.name.strftime('%Y-%m-%d')
            }
        
        else:
            # Yahoo Finance for US stocks
            def get_yf_data():
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period="2d")
                return info, hist
            
            loop = asyncio.get_event_loop()
            info, hist = await loop.run_in_executor(executor, get_yf_data)
            
            if hist.empty:
                return {"error": f"US stock '{symbol}' not found"}
            
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            
            change = latest['Close'] - prev['Close']
            change_pct = (change / prev['Close'] * 100) if prev['Close'] != 0 else 0
            
            return {
                "symbol": symbol,
                "exchange": info.get("exchange", "US Market"),
                "price": f"${latest['Close']:.2f}",
                "change": f"${change:.2f}",
                "change_percent": f"{change_pct:.2f}%",
                "volume": f"{int(latest['Volume']):,}",
                "market_cap": f"${info.get('marketCap', 0):,}" if info.get('marketCap') else "N/A",
                "last_updated": latest.name.strftime('%Y-%m-%d')
            }
    
    except Exception as e:
        return {"error": f"Failed to fetch stock price: {str(e)}"}


@mcp.tool()
async def get_stock_history(symbol: str, start_date: str, end_date: str) -> dict:
    """
    Get historical stock prices for a specific date range.
    
    Args:
        symbol: Stock ticker (e.g., 'VNM', 'AAPL')
        start_date: Start date in YYYY-MM-DD format (e.g., '2025-09-15')
        end_date: End date in YYYY-MM-DD format (e.g., '2025-09-20')
    
    Returns:
        Historical price data for the date range
    """
    symbol = symbol.upper()
    
    try:
        # Add .VN suffix for Vietnamese stocks
        yf_symbol = f"{symbol}.VN" if is_vietnamese_stock(symbol) else symbol
        
        def get_yf_history():
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(start=start_date, end=end_date)
            return hist
        
        loop = asyncio.get_event_loop()
        hist = await loop.run_in_executor(executor, get_yf_history)
        
        if hist.empty:
            return {
                "error": f"No historical data for {symbol} in the specified date range",
                "tip": "Make sure dates are in the past and market was open"
            }
        
        history = []
        is_vn = is_vietnamese_stock(symbol)
        
        for date, row in hist.iterrows():
            if is_vn:
                history.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "close": f"{row['Close']:,.0f} VND",
                    "open": f"{row['Open']:,.0f} VND",
                    "high": f"{row['High']:,.0f} VND",
                    "low": f"{row['Low']:,.0f} VND",
                    "volume": f"{int(row['Volume']):,}"
                })
            else:
                history.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "close": f"${row['Close']:.2f}",
                    "open": f"${row['Open']:.2f}",
                    "high": f"${row['High']:.2f}",
                    "low": f"${row['Low']:.2f}",
                    "volume": f"{int(row['Volume']):,}"
                })
        
        return {
            "symbol": symbol,
            "exchange": "Vietnam" if is_vn else "US Market",
            "start_date": start_date,
            "end_date": end_date,
            "data_points": len(history),
            "history": history
        }
    
    except Exception as e:
        return {"error": f"Failed to get historical data: {str(e)}"}


@mcp.tool()
async def get_company_overview(symbol: str) -> dict:
    """
    Get detailed company information.
    
    Args:
        symbol: Stock ticker (US: 'AAPL' | VN: 'VNM', 'VCB')
    
    Returns:
        Dictionary with company overview data
    """
    symbol = symbol.upper()
    
    try:
        if is_vietnamese_stock(symbol):
            # VNDirect API for VN company data
            url = f"https://finfo-api.vndirect.com.vn/v4/stocks/{symbol}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                data = response.json()
            
            if not data or "code" in data:
                # Fallback to Yahoo Finance
                yf_symbol = f"{symbol}.VN"
                
                def get_yf_info():
                    ticker = yf.Ticker(yf_symbol)
                    return ticker.info
                
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(executor, get_yf_info)
                
                return {
                    "symbol": symbol,
                    "name": info.get('longName', 'N/A'),
                    "exchange": "Vietnam",
                    "industry": info.get('industry', 'N/A'),
                    "sector": info.get('sector', 'N/A'),
                    "website": info.get('website', 'N/A'),
                    "description": info.get('longBusinessSummary', 'N/A')[:500],
                    "employees": info.get('fullTimeEmployees', 'N/A'),
                    "market_cap": f"{info.get('marketCap', 0):,.0f} VND" if info.get('marketCap') else "N/A"
                }
            
            return {
                "symbol": symbol,
                "name": data.get('companyName', 'N/A'),
                "exchange": data.get('exchange', 'Vietnam'),
                "industry": data.get('industryName', 'N/A'),
                "sector": data.get('icbName', 'N/A'),
                "website": data.get('website', 'N/A'),
                "employees": data.get('noEmployees', 'N/A'),
                "listing_date": data.get('issueDate', 'N/A'),
                "outstanding_shares": f"{data.get('outstandingShare', 0):,.0f}",
                "charter_capital": f"{data.get('charteredCapital', 0):,.0f} VND"
            }
        
        else:
            # Yahoo Finance for US stocks
            def get_yf_info():
                ticker = yf.Ticker(symbol)
                return ticker.info
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(executor, get_yf_info)
            
            if not info or 'symbol' not in info:
                return {"error": f"Company data for '{symbol}' not found"}
            
            return {
                "symbol": symbol,
                "name": info.get("longName", "N/A"),
                "exchange": info.get("exchange", "US Market"),
                "description": info.get("longBusinessSummary", "N/A")[:500] + "...",
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": f"${info.get('marketCap', 0):,}" if info.get('marketCap') else "N/A",
                "pe_ratio": info.get("trailingPE", "N/A"),
                "dividend_yield": f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "N/A",
                "52_week_high": f"${info.get('fiftyTwoWeekHigh', 0):.2f}" if info.get('fiftyTwoWeekHigh') else "N/A",
                "52_week_low": f"${info.get('fiftyTwoWeekLow', 0):.2f}" if info.get('fiftyTwoWeekLow') else "N/A",
                "employees": info.get("fullTimeEmployees", "N/A"),
                "website": info.get("website", "N/A")
            }
    
    except Exception as e:
        return {"error": f"Failed to fetch company overview: {str(e)}"}


@mcp.tool()
async def get_vn_company_financials(symbol: str) -> dict:
    """
    Get comprehensive financial metrics for Vietnamese companies.
    
    Args:
        symbol: Vietnamese stock ticker (e.g., 'VNM', 'VCB', 'FPT')
    
    Returns:
        Dictionary with detailed financial metrics
    """
    try:
        symbol = symbol.upper()
        
        # Try Yahoo Finance first (fastest)
        yf_symbol = f"{symbol}.VN"
        
        def get_yf_info():
            ticker = yf.Ticker(yf_symbol)
            return ticker.info
        
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(executor, get_yf_info)
        
        # Also try VNDirect for additional data
        url = f"https://finfo-api.vndirect.com.vn/v4/ratios"
        params = {"q": f"code:{symbol}", "size": 1}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                vnd_data = response.json()
            vnd_info = vnd_data["data"][0] if vnd_data.get("data") else {}
        except:
            vnd_info = {}
        
        return {
            "symbol": symbol,
            "market_cap": f"{info.get('marketCap', 0):,.0f} VND" if info.get('marketCap') else "N/A",
            "pe_ratio": info.get("trailingPE") or vnd_info.get("pe", "N/A"),
            "pb_ratio": info.get("priceToBook") or vnd_info.get("pb", "N/A"),
            "ps_ratio": vnd_info.get("ps", "N/A"),
            "roe": f"{vnd_info.get('roe', 0):.2f}%" if vnd_info.get('roe') else "N/A",
            "roa": f"{vnd_info.get('roa', 0):.2f}%" if vnd_info.get('roa') else "N/A",
            "eps": info.get("trailingEps") or vnd_info.get("eps", "N/A"),
            "book_value_per_share": f"{info.get('bookValue', 0):,.0f} VND" if info.get('bookValue') else "N/A",
            "dividend_yield": f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "N/A",
            "profit_margin": f"{info.get('profitMargins', 0) * 100:.2f}%" if info.get('profitMargins') else "N/A",
            "debt_to_equity": info.get("debtToEquity") or vnd_info.get("debtOverEquity", "N/A"),
            "current_ratio": info.get("currentRatio") or vnd_info.get("currentRatio", "N/A"),
            "revenue_growth": f"{info.get('revenueGrowth', 0) * 100:.2f}%" if info.get('revenueGrowth') else "N/A"
        }
    
    except Exception as e:
        return {"error": f"Failed to get financial data: {str(e)}"}


@mcp.tool()
async def get_market_news(query: str = "stock market", language: str = "en", limit: int = 5) -> dict:
    """
    Get latest financial news.
    
    Args:
        query: Search query (e.g., 'VNM stock', 'Apple')
        language: 'en' for English or 'vi' for Vietnamese
        limit: Number of articles (1-10)
    
    Returns:
        Dictionary with news articles
    """
    try:
        limit = min(max(1, limit), 10)
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",
            "language": language if language == "en" else "en",
            "pageSize": limit,
            "apiKey": NEWS_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
        
        if data.get("status") != "ok":
            return {"error": "Failed to fetch news", "tip": "Check API key"}
        
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
async def search_vietnamese_stocks(keywords: str) -> dict:
    """
    Search for Vietnamese stocks by company name.
    
    Args:
        keywords: Company name in Vietnamese (e.g., 'Vinamilk', 'Vietcombank')
    
    Returns:
        List of matching Vietnamese stocks
    """
    try:
        url = "https://finfo-api.vndirect.com.vn/v4/stocks"
        params = {
            "q": f"companyName~{keywords}",
            "size": 10
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()
        
        if not data or "data" not in data or not data["data"]:
            return {"error": "No matching stocks found"}
        
        matches = []
        for item in data["data"]:
            matches.append({
                "symbol": item.get("code", "N/A"),
                "name": item.get("companyName", "N/A"),
                "exchange": item.get("exchange", "N/A"),
                "industry": item.get("industryName", "N/A")
            })
        
        return {
            "query": keywords,
            "matches": matches
        }
    
    except Exception as e:
        return {"error": f"Failed to search stocks: {str(e)}"}


@mcp.tool()
async def get_vn_index() -> dict:
    """
    Get current VN-Index (Vietnamese stock market index).
    
    Returns:
        Dictionary with VN-Index data
    """
    try:
        def get_yf_index():
            ticker = yf.Ticker("^VNINDEX")
            hist = ticker.history(period="2d")
            return hist
        
        loop = asyncio.get_event_loop()
        hist = await loop.run_in_executor(executor, get_yf_index)
        
        if hist.empty:
            return {"error": "Failed to fetch VN-Index"}
        
        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else latest
        
        change = latest['Close'] - prev['Close']
        change_pct = (change / prev['Close'] * 100) if prev['Close'] != 0 else 0
        
        return {
            "index": "VN-Index",
            "value": f"{latest['Close']:,.2f}",
            "change": f"{change:,.2f}",
            "change_percent": f"{change_pct:.2f}%",
            "volume": f"{int(latest['Volume']):,}",
            "date": latest.name.strftime('%Y-%m-%d')
        }
    
    except Exception as e:
        return {"error": f"Failed to fetch VN-Index: {str(e)}"}


if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="stdio")