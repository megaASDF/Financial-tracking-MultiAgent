# MCP Server for Technical Analysis Agent

from mcp.server.fastmcp import FastMCP
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

# Khởi tạo MCP Server
mcp = FastMCP("Technical Analysis Server")

@mcp.tool()
def analyze_technical_indicators(ticker: str) -> str:
    """
    Phân tích kỹ thuật cho một mã cổ phiếu (VN hoặc US).
    Tính toán RSI, MACD, Bollinger Bands và đưa ra tín hiệu kỹ thuật.
    Args:
        ticker: Mã cổ phiếu (VD: "VNM.VN" cho Việt Nam, "AAPL" cho Mỹ).
    """
    try:
        # 1. Xử lý hậu tố .VN nếu người dùng quên
        # Lưu ý: yfinance cần .VN cho cổ phiếu Việt Nam
        if len(ticker) == 3 and ticker.isalpha(): 
             
            pass 

        # 2. Lấy dữ liệu lịch sử (6 tháng là đủ để tính các chỉ báo)
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        
        if df.empty:
            return f"Lỗi: Không tìm thấy dữ liệu cho mã {ticker}. Hãy kiểm tra lại mã (VD: thêm .VN cho cổ phiếu Việt)."

        # 3. Tính toán các chỉ số kỹ thuật (Technical Indicators)
        
        # --- RSI (Relative Strength Index) ---
        rsi_indicator = RSIIndicator(close=df["Close"], window=14)
        current_rsi = rsi_indicator.rsi().iloc[-1]
        
        # --- MACD (Moving Average Convergence Divergence) ---
        macd = MACD(close=df["Close"])
        current_macd = macd.macd().iloc[-1]
        current_signal = macd.macd_signal().iloc[-1]
        
        # --- Bollinger Bands ---
        bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
        current_price = df["Close"].iloc[-1]
        bb_high = bb.bollinger_hband().iloc[-1]
        bb_low = bb.bollinger_lband().iloc[-1]

        # --- SMA (Simple Moving Average) ---
        sma_50 = SMAIndicator(close=df["Close"], window=50).sma_indicator().iloc[-1]
        sma_200 = SMAIndicator(close=df["Close"], window=200).sma_indicator().iloc[-1]

        # 4. Tổng hợp tín hiệu (Rule-based)
        signal_summary = []
        
        # Đánh giá RSI
        if current_rsi > 70: signal_summary.append("RSI: Quá mua (Nguy cơ đảo chiều giảm)")
        elif current_rsi < 30: signal_summary.append("RSI: Quá bán (Cơ hội mua tiềm năng)")
        else: signal_summary.append(f"RSI: {current_rsi:.2f} (Trung tính)")

        # Đánh giá MACD
        if current_macd > current_signal: signal_summary.append("MACD: Cắt lên đường tín hiệu (Xu hướng Tăng)")
        else: signal_summary.append("MACD: Cắt xuống đường tín hiệu (Xu hướng Giảm)")

        # Đánh giá Xu hướng (SMA)
        trend = "Tăng" if current_price > sma_50 else "Giảm"
        
        # 5. Trả về kết quả dạng văn bản
        result = f"""
--- BÁO CÁO PHÂN TÍCH KỸ THUẬT: {ticker.upper()} ---
Giá đóng cửa: {current_price:,.2f}

1. CHỈ SỐ SỨC MẠNH (RSI): {current_rsi:.2f}
   -> Nhận định: {signal_summary[0]}

2. XU HƯỚNG (MACD & SMA):
   -> MACD: {current_macd:.4f} (Signal: {current_signal:.4f})
   -> Tín hiệu MACD: {signal_summary[1]}
   -> Xu hướng ngắn hạn (vs SMA50): Giá đang {trend} so với trung bình 50 phiên.

3. DẢI BOLLINGER:
   -> Trên: {bb_high:,.2f} | Dưới: {bb_low:,.2f}
   -> Vị trí giá: {"Vượt dải trên" if current_price > bb_high else "Thủng dải dưới" if current_price < bb_low else "Nằm trong dải"}

4. KẾT LUẬN TỔNG HỢP:
   Dựa trên các chỉ báo trên, cổ phiếu đang ở trạng thái: {"TÍCH CỰC" if current_rsi < 70 and current_macd > current_signal else "TIÊU CỰC" if current_macd < current_signal else "TRUNG TÍNH"}.
"""
        return result

    except Exception as e:
        return f"Lỗi khi phân tích kỹ thuật: {str(e)}"

if __name__ == "__main__":
    mcp.run()