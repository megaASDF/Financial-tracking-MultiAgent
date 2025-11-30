import sys
import os

# Fix Windows console encoding 
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except:
    pass

# Set absolute paths 
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Set database path as environment variable for models.py
os.environ['PORTFOLIO_DB_PATH'] = os.path.join(SCRIPT_DIR, 'database', 'portfolio.db')

# Force stderr to be unbuffered (critical for MCP protocol)
sys.stderr.reconfigure(line_buffering=True)
sys.stdout.reconfigure(line_buffering=True)

# Minimal debug output
print(f"[INIT] Script dir: {SCRIPT_DIR}", file=sys.stderr, flush=True)
print(f"[INIT] DB path: {os.environ['PORTFOLIO_DB_PATH']}", file=sys.stderr, flush=True)


from mcp.server.fastmcp import FastMCP

try:
    from database.models import (
        add_transaction,
        get_all_positions,
        get_current_price,
        get_transaction_history,
        get_realized_pnl_summary,
        clear_all_data,
        validate_ticker
    )
    print("[INIT] database.models imported", file=sys.stderr, flush=True)
except Exception as e:
    print(f"[FATAL] models import failed: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

# Khởi tạo MCP Server
mcp = FastMCP("Portfolio Manager")

# Helper functions (FORMATTING) 
def format_currency(amount: float, market: str = "VN") -> str:
    """Format số tiền theo market"""
    if market == "VN":
        return f"{amount:,.0f} VNĐ"
    else:
        return f"${amount:,.2f}"

def format_percent(value: float) -> str:
    """Format phần trăm với dấu +/-"""
    return f"{value:+.2f}%"

def get_emoji(percent: float) -> str:
    """Chọn emoji dựa trên % thay đổi"""
    if percent > 5:
        return "🎉"
    elif percent < -5:
        return "⚠️"
    else:
        return "📊"


@mcp.tool()
def buy_stock(ticker: str, quantity: int, price: float,market: str = "VN", notes: str = "") -> str:
    """Mua cổ phiếu và thêm vào danh mục.
    Args:
        ticker: Mã cổ phiếu (VD: VNM, AAPL)
        quantity: Số lượng cổ phiếu
        price: Giá mua (VNĐ hoặc USD)
        market: Thị trường "VN" hoặc "US" (mặc định VN)
        notes: Ghi chú (tùy chọn)

    Returns:
        Thông báo kết quả giao dịch
    """
    try:
        # Validate inputs
        if quantity <= 0:
            return "❌ Lỗi: Số lượng phải lớn hơn 0"
        
        if price <= 0:
            return "❌ Lỗi: Giá phải lớn hơn 0"
        
        market = market.upper()
        if market not in ["VN", "US"]:
            return "❌ Lỗi: Market phải là 'VN' hoặc 'US'"
        
        ticker = ticker.upper()
        
        # Validate ticker exists
        is_valid = validate_ticker(ticker, market)
        if not is_valid:
            return f"❌ Lỗi: Mã {ticker} không tồn tại trên thị trường {market}"
        
        # Execute transaction
        result = add_transaction(
            ticker=ticker,
            trans_type='BUY',
            quantity=quantity,
            price=price,
            market=market,
            notes=notes
        )
        
        if result['success']:
            total_value = quantity * price
            return (
                f"✅ {result['message']}\n\n"
                f"**Chi tiết giao dịch:**\n"
                f"- Mã CP: `{ticker}`\n"
                f"- Số lượng: {quantity:,} cp\n"
                f"- Giá mua: {format_currency(price, market)}\n"
                f"- Tổng tiền: {format_currency(total_value, market)}\n"
                f"- Thị trường: {market}\n"
                f"{f'- Ghi chú: {notes}' if notes else ''}"
            )
        else:
            return f"❌ {result['message']}"
            
    except Exception as e:
        return f"❌ Lỗi không mong đợi: {str(e)}"

@mcp.tool()
def sell_stock(ticker: str, quantity: int, price: float, market: str = "VN", notes: str = "") -> str:
    """
    Bán cổ phiếu và tự động tính realized P&L
    
    Args:
        ticker: Mã cổ phiếu (VD: VNM, AAPL)
        quantity: Số lượng cổ phiếu cần bán
        price: Giá bán (VNĐ hoặc USD)
        market: Thị trường "VN" hoặc "US" (mặc định VN)
        notes: Ghi chú (tùy chọn)
    
    Returns:
        Thông báo kết quả + realized P&L
    """
    try:
        # Validate inputs
        if quantity <= 0:
            return "❌ Lỗi: Số lượng phải lớn hơn 0"
        
        if price <= 0:
            return "❌ Lỗi: Giá phải lớn hơn 0"
        
        market = market.upper()
        if market not in ["VN", "US"]:
            return "❌ Lỗi: Market phải là 'VN' hoặc 'US'"
        
        ticker = ticker.upper()
        
        # Execute transaction
        result = add_transaction(
            ticker=ticker,
            trans_type='SELL',
            quantity=quantity,
            price=price,
            market=market,
            notes=notes
        )
        
        if result['success']:
            pnl_data = result.get('pnl_data', {})
            
            response = f"✅ {result['message']}\n\n"
            response += f"**Chi tiết giao dịch:**\n"
            response += f"- Mã CP: `{ticker}`\n"
            response += f"- Số lượng: {quantity:,} cp\n"
            response += f"- Giá bán: {format_currency(price, market)}\n"
            response += f"- Tổng tiền: {format_currency(quantity * price, market)}\n"
            
            # Add P&L info if available
            if pnl_data:
                pnl_amount = pnl_data.get('pnl', 0)
                pnl_percent = pnl_data.get('pnl_percent', 0)
                emoji = get_emoji(pnl_percent)
                
                response += f"\n**Kết quả đầu tư:**\n"
                response += f"- Giá mua TB: {format_currency(pnl_data.get('buy_price', 0), market)}\n"
                response += f"- Lãi/Lỗ: {emoji} {format_currency(pnl_amount, market)} ({format_percent(pnl_percent)})\n"
            
            if notes:
                response += f"\n- Ghi chú: {notes}"
            
            return response
        else:
            return f"❌ {result['message']}"
            
    except Exception as e:
        return f"❌ Lỗi không mong đợi: {str(e)}"

@mcp.tool()
def view_portfolio() -> str:
    """
    Xem tổng quan danh mục đầu tư với unrealized P&L realtime
    
    Returns:
        Bảng markdown hiển thị tất cả vị thế hiện tại    
    """
    try:
        positions = get_all_positions()
        
        if not positions:
            return " Danh mục của bạn đang trống. Hãy mua cổ phiếu đầu tiên!"
        
        # Build markdown table
        output = "# Danh Mục Đầu Tư\n\n"
        output += "| Mã CP | SL | Giá Mua TB | Giá Hiện Tại | Lãi/Lỗ | % | Market |\n"
        output += "|-------|----:|------------:|-------------:|-------:|---:|--------|\n"
        
        total_invested = 0
        total_current_value = 0
        
        for pos in positions:
            ticker = pos['ticker']
            quantity = pos['quantity']
            avg_price = pos['avg_buy_price']
            market = pos['market']
            
            # Get current price (cached 5 mins)
            current_price = get_current_price(ticker, market)
            
            if current_price:
                invested = avg_price * quantity
                current_value = current_price * quantity
                pnl = current_value - invested
                pnl_percent = (pnl / invested) * 100
                emoji = get_emoji(pnl_percent)
                
                total_invested += invested
                total_current_value += current_value
                
                output += (
                    f"| {ticker} | {quantity:,} | "
                    f"{format_currency(avg_price, market)} | "
                    f"{format_currency(current_price, market)} | "
                    f"{emoji} {format_currency(pnl, market)} | "
                    f"{format_percent(pnl_percent)} | {market} |\n"
                )
            else:
                output += (
                    f"| {ticker} | {quantity:,} | "
                    f"{format_currency(avg_price, market)} | "
                    f" Đang lấy... | - | - | {market} |\n"
                )
        
        # Summary
        if total_invested > 0:
            total_pnl = total_current_value - total_invested
            total_pnl_percent = (total_pnl / total_invested) * 100
            emoji = get_emoji(total_pnl_percent)
            
            output += f"\n**Tổng quan:**\n"
            output += f"- Tổng vốn đầu tư: {format_currency(total_invested, 'VN')}\n"
            output += f"- Giá trị hiện tại: {format_currency(total_current_value, 'VN')}\n"
            output += f"- Tổng lãi/lỗ: {emoji} {format_currency(total_pnl, 'VN')} ({format_percent(total_pnl_percent)})\n"
        
        output += f"\n*Cập nhật: {positions[0]['last_updated']} (GMT+7)*"
        output += f"\n*Giá cached 5 phút để tránh spam API*"
        
        return output
        
    except Exception as e:
        return f"❌ Lỗi khi load danh mục: {str(e)}"

@mcp.tool()
def view_history(ticker: str = None, limit: int = 20) -> str:
    """
    Xem lịch sử giao dịch
    
    Args:
        ticker: Lọc theo mã cổ phiếu (tùy chọn, để trống = tất cả)
        limit: Số giao dịch hiển thị (mặc định 20)
    
    Returns:
        Bảng markdown lịch sử giao dịch
    """
    try:
        if ticker:
            ticker = ticker.upper()
        
        transactions = get_transaction_history(ticker, limit)
        
        if not transactions:
            if ticker:
                return f"📭 Không có giao dịch nào cho mã {ticker}"
            else:
                return "📭 Chưa có giao dịch nào trong hệ thống"
        
        # Build markdown table
        output = f"# Lịch Sử Giao Dịch{f' - {ticker}' if ticker else ''}\n\n"
        output += "| Ngày | Giờ | Loại | Mã CP | SL | Giá | Tổng tiền | Market | Ghi chú |\n"
        output += "|------|-----|------|-------|----:|----:|----------:|--------|----------|\n"
        
        for tx in transactions:
            tx_type_icon = "🟢" if tx['type'] == 'BUY' else "🔴"
            total = tx['quantity'] * tx['price']
            notes_display = tx['notes'][:20] + "..." if len(tx['notes']) > 20 else tx['notes']
            
            output += (
                f"| {tx['date']} | {tx['time']} | "
                f"{tx_type_icon} {tx['type']} | "
                f"{tx['ticker']} | {tx['quantity']:,} | "
                f"{format_currency(tx['price'], tx['market'])} | "
                f"{format_currency(total, tx['market'])} | "
                f"{tx['market']} | {notes_display} |\n"

            )
                
        return output
        
    except Exception as e:
        return f"❌ Lỗi khi load lịch sử: {str(e)}"

@mcp.tool()
def view_performance(ticker: str = None) -> str:
    """
    Xem hiệu suất đầu tư (realized P&L, win rate)
    
    Args:
        ticker: Lọc theo mã cổ phiếu (tùy chọn)
    
    Returns:
        Báo cáo tổng hợp hiệu suất
    """
    try:
        if ticker:
            ticker = ticker.upper()
        
        summary = get_realized_pnl_summary(ticker)
        
        if not summary:
            if ticker:
                return f"📭 Chưa có giao dịch chốt lời/lỗ nào cho {ticker}"
            else:
                return "📭 Chưa có giao dịch chốt lời/lỗ nào"
        
        # Calculate statistics
        total_trades = summary['total_trades']
        total_pnl = summary['total_pnl']
        # avg_pnl = summary['avg_pnl']
        winning_trades = summary['winning_trades']
        losing_trades = summary['losing_trades']
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        lose_rate = (losing_trades / total_trades * 100) if total_trades > 0 else 0
        # Determine overall emoji
        emoji = get_emoji(total_pnl)
        
        # Build report
        output = f"# 📈 Báo Cáo Hiệu Suất{f' - {ticker}' if ticker else ''}\n\n"
        
        output += f"**Tổng quan:**\n"
        output += f"- Tổng giao dịch: {total_trades}\n"
        output += f"- Thắng: 🟢 {winning_trades} ({win_rate:.1f}%)\n"
        output += f"- Thua: 🔴 {losing_trades} ({lose_rate:.1f}%)\n"
        output += f"\n**Kết quả tài chính:**\n"
        output += f"- Tổng lãi/lỗ: {emoji} {format_currency(total_pnl, 'VN')}\n"
        # output += f"- Trung bình/giao dịch: {format_currency(avg_pnl, 'VN')}\n"
        
        # Performance assessment
        if win_rate >= 60:
            assessment = "🎉 Xuất sắc! Tỷ lệ thắng cao"
        elif win_rate >= 50:
            assessment = "👍 Tốt! Tỷ lệ thắng ổn định"
        elif win_rate >= 40:
            assessment = "⚠️ Cần cải thiện chiến lược"
        else:
            assessment = "🚨 Nên xem xét lại phương pháp đầu tư"
        
        output += f"\n**Đánh giá:** {assessment}"
        
        return output
        
    except Exception as e:
        return f"❌ Lỗi khi tính hiệu suất: {str(e)}"

@mcp.tool()
def reset_portfolio() -> str:
    """
    ⚠️ XÓA TOÀN BỘ dữ liệu portfolio (transactions, positions, P&L)
    
    CẢNH BÁO: Hành động này KHÔNG THỂ HOÀN TÁC!
    
    Returns:
        Thông báo kết quả
    """
    try:
        result = clear_all_data()
        
        if result['success']:
            return (
                f"✅ {result['message']}\n\n"
                f"🗑️ Đã xóa:\n"
                f"- Tất cả giao dịch mua/bán\n"
                f"- Tất cả vị thế hiện tại\n"
                f"- Lịch sử lãi/lỗ đã chốt\n"
                f"- Cache giá cổ phiếu\n\n"
                f"Bạn có thể bắt đầu lại với danh mục mới!"
            )
        else:
            return f"❌ {result['message']}"
            
    except Exception as e:
        return f"❌ Lỗi khi reset: {str(e)}"

if __name__ == "__main__":
    print("[INIT] Starting MCP server...", file=sys.stderr, flush=True)
    try:
        mcp.run()
    except Exception as e:
        print(f"[FATAL] Server crashed: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)