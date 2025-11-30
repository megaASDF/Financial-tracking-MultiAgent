"""
Debug script - Test portfolio tools trực tiếp
Chạy: python debug_portfolio_tools.py
"""

import sys
import os

# Setup paths
script_dir = os.path.dirname(os.path.abspath(__file__))
finance_mcp_dir = os.path.join(script_dir, "finance_mcp_server")
sys.path.insert(0, finance_mcp_dir)

# Set DB path
os.environ['PORTFOLIO_DB_PATH'] = os.path.join(finance_mcp_dir, 'database', 'portfolio.db')

# Fix encoding
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except:
    pass

print("="*70)
print("🔍 DEBUGGING PORTFOLIO TOOLS")
print("="*70)

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

# Test 1: Import models
print("\n[TEST 1] Importing database.models...")
try:
    from database.models import (
        add_transaction,
        get_all_positions,
        get_realized_pnl_summary,
        get_transaction_history,
        get_current_price,
        clear_all_data
    )
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Database path
# print(f"\n[TEST 2] Database path: {os.environ.get('PORTFOLIO_DB_PATH')}")
# db_exists = os.path.exists(os.environ['PORTFOLIO_DB_PATH'])
# print(f"  Database exists: {'✅' if db_exists else '❌'}")


# Test 4: Get positions
# print("\n[TEST 4] Getting positions...")
# try:
#     positions = get_all_positions()
#     print(f"  Type: {type(positions)}")
#     print(f"  Count: {len(positions) if positions else 0}")
    
#     if positions:
#         print("  ✅ Positions retrieved:")
#         output = "# Danh Mục Đầu Tư\n\n"
#         output += "| Mã CP | SL | Giá Mua TB | Giá Hiện Tại | Lãi/Lỗ | % | Market |\n"
#         output += "|-------|----:|------------:|-------------:|-------:|---:|--------|\n"
        
#         total_invested = 0
#         total_current_value = 0

#         for pos in positions:
#             ticker = pos['ticker']
#             quantity = pos['quantity']
#             avg_price = pos['avg_buy_price']
#             market = pos['market']
            
#             # Get current price (cached 5 mins)
#             current_price = get_current_price(ticker, market)
            
#             if current_price:
#                 invested = avg_price * quantity
#                 current_value = current_price * quantity
#                 pnl = current_value - invested
#                 pnl_percent = (pnl / invested) * 100
#                 emoji = get_emoji(pnl_percent)
                
#                 total_invested += invested
#                 total_current_value += current_value
                
#                 output += (
#                     f"| {ticker} | {quantity:,} | "
#                     f"{format_currency(avg_price, market)} | "
#                     f"{format_currency(current_price, market)} | "
#                     f"{emoji} {format_currency(pnl, market)} | "
#                     f"{format_percent(pnl_percent)} | {market} |\n"
#                 )
#             else:
#                 output += (
#                     f"| {ticker} | {quantity:,} | "
#                     f"{format_currency(avg_price, market)} | "
#                     f" Đang lấy... | - | - | {market} |\n"
#                 )
#         if total_invested > 0:
#             total_pnl = total_current_value - total_invested
#             total_pnl_percent = (total_pnl / total_invested) * 100
#             emoji = get_emoji(total_pnl_percent)
            
#             output += f"\n**Tổng quan:**\n"
#             output += f"- Tổng vốn đầu tư: {format_currency(total_invested, 'VN')}\n"
#             output += f"- Giá trị hiện tại: {format_currency(total_current_value, 'VN')}\n"
#             output += f"- Tổng lãi/lỗ: {emoji} {format_currency(total_pnl, 'VN')} ({format_percent(total_pnl_percent)})\n"
        
#         output += f"\n*Cập nhật: {positions[0]['last_updated']} (GMT+7)*"
#         output += f"\n*Giá cached 5 phút để tránh spam API*"
#         print(output)
#     else:
#         print("  ⚠️ No positions found")
        
# except Exception as e:
#     print(f"  ❌ Exception: {e}")
#     import traceback
#     traceback.print_exc()

print("\n[TEST 3] View performance...")
try:
    summary = get_realized_pnl_summary()
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
    output = ""
    
    output += f"**Tổng quan:**\n"
    output += f"- Tổng giao dịch: {total_trades}\n"
    output += f"- Thắng: 🟢 {winning_trades} ({win_rate:.1f}%)\n"
    output += f"- Thua: 🔴 {losing_trades} ({lose_rate:.1f}%)\n"
    output += f"\n**Kết quả tài chính:**\n"
    output += f"- Tổng lãi/lỗ: {emoji} {format_currency(total_pnl, 'VN')}\n"
     
    
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

    print(output)
except Exception as e:
    print(f"  ❌ Exception: {e}")
    import traceback
    traceback.print_exc()

# print("\n[TEST 5] Getting transaction history...")
# try:
#     history = get_transaction_history()
#     print(f"  Type: {type(history)}")
#     print(f"  Count: {len(history) if history else 0}")
    
#     if history:
#         print("  ✅ History retrieved:")
#         output = ""
#         output += "| Ngày | Giờ | Loại | Mã CP | SL | Giá | Tổng tiền | Market | Ghi chú |\n"
#         output += "|------|-----|------|-------|----:|----:|----------:|--------|----------|\n"
        
#         for tx in history:  
#             tx_type_icon = "🟢" if tx['type'] == 'BUY' else "🔴"
#             total = tx['quantity'] * tx['price']
#             notes_display = tx['notes'][:20] + "..." if len(tx['notes']) > 20 else tx['notes']
#             output += (
#                 f"| {tx['date']} | {tx['time']} | "
#                 f"{tx_type_icon} {tx['type']} | "
#                 f"{tx['ticker']} | {tx['quantity']:,} | "
#                 f"{format_currency(tx['price'], tx['market'])} | "
#                 f"{format_currency(total, tx['market'])} | "
#                 f"{tx['market']} | {notes_display} |\n"

#             )
#         print(output)
#     else:
#         print("  ⚠️ No history found")
        
# except Exception as e:
#     print(f"  ❌ Exception: {e}")
#     import traceback
#     traceback.print_exc()



# Summary
print("\n" + "="*70)
print("📊 SUMMARY")
print("="*70)

positions = get_all_positions()
print(f"Positions count: {len(positions) if positions else 0}")

print("\n💡 NEXT STEPS:")
print("1. If all tests pass ✅, the issue is in MCP communication")
print("2. If tests fail ❌, check the error messages above")
print("3. Run: python agent.py and try 'mua 5 VNM giá 62000'")
print("="*70)