# agent.py
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows console encoding first
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except:
    pass

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.agent_tool import AgentTool
from mcp import StdioServerParameters
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams


# --- Get the absolute path to THIS script's directory (multiagent) ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# --- Get absolute paths to MCP servers ---
finance_mcp_dir = os.path.abspath(os.path.join(script_dir, "..", "finance_mcp_server"))
server_script_path = os.path.join(finance_mcp_dir, "server.py")
technical_server_path = os.path.join(finance_mcp_dir, "technical_server.py")
portfolio_server_path = os.path.join(finance_mcp_dir, "portfolio_server.py")

# --- Get the absolute path to the current Python executable ---
python_executable_path = sys.executable

print("="*60)
print(f"Agent directory is: {script_dir}")
print(f"Attempting to launch MCP server at: {server_script_path}")
print(f"Technical Analysis server at: {technical_server_path}")
print(f"Portfolio Management server at: {portfolio_server_path}")
print(f"Using Python interpreter: {python_executable_path}")
print("="*60)

# FIXED: Increase timeout to 30 seconds for slow API calls
# Create MCP Toolset for Financial-info MCP Server
mcp_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command=python_executable_path,
        args=[server_script_path],
        env=None
    )
)

# Create MCP Toolset for Technical Analysis MCP Server
technical_mcp_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command=python_executable_path,
        args=[technical_server_path],
        env=None
    )
)

# Create MCP Toolset for Portfolio Management MCP Server
portfolio_mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=python_executable_path,
            args=[portfolio_server_path],
            env=None
        ),
        timeout=150, # 2.5 minutes timeout
    ),
)


# Create Agents
# Agent 1: Search Agent
search_agent = Agent(
    model='gemini-2.5-flash', 
    name='search_agent',
    instruction='''You're a specialist in Google Search''',
    tools=[google_search],
)

# Agent 2: Finance Information Agent
finance_info_agent = Agent(
    model='gemini-2.5-flash',
    name='finance_info_agent',
    instruction='''
    Bạn là một chuyên gia trong việc cung cấp thông tin tài chính về cổ phiếu, công ty và xu hướng thị trường.
    Nhiệm vụ của bạn:
- Phân tích và cung cấp thông tin về cổ phiếu Việt Nam (VNM, FPT...) và Mỹ (AAPL, GOOGL...).
- Kiểm tra chỉ số VN-Index.
- Tìm kiếm cổ phiếu.
- Cập nhật tin tức thị trường.
- Phân tích bao cáo tài chính cơ bản của công ty. 

QUY TẮC SỬ DỤNG CÔNG CỤ (Âm thầm thực hiện):
- Nếu hỏi giá HIỆN TẠI: Dùng 'get_stock_price'.
- Nếu hỏi giá trong QUÁ KHỨ (có ngày tháng, "tháng trước"...): Dùng 'get_stock_history' (định dạng YYYY-MM-DD).
- Nếu hỏi chỉ số tài chính VN (P/E, ROE...): Dùng 'get_vn_company_financials'.
- Nếu hỏi thông tin TỔNG QUAN công ty: Dùng 'get_company_overview'.
- Nếu tìm mã cổ phiếu VN: Dùng 'search_vietnamese_stocks'.
- Nếu cần tin tức: Dùng 'get_market_news'.
''',
    tools=[mcp_toolset]
)

# Agent 3: Technical Analysis Agent
technical_analyst_agent = Agent(
    model='gemini-2.5-flash',   
    name='technical_analyst_agent',
    instruction='''
    Bạn là một chuyên gia Phân Tích Kỹ Thuật (Technical Analyst).
    Nhiệm vụ: Sử dụng công cụ để tính toán chỉ số và đưa ra nhận định chi tiết.

    QUY TẮC TRẢ LỜI (BẮT BUỘC TUÂN THỦ):
    Dù người dùng hỏi ngắn hay dài, câu trả lời của bạn LUÔN LUÔN phải bao gồm 3 phần sau:

    1. PHÂN TÍCH SỐ LIỆU (Trích xuất từ tool):
       - RSI: [Giá trị] -> [Nhận định: Quá mua/Quá bán/Trung tính]
       - MACD: [Giá trị] -> [Nhận định: Cắt lên hay Cắt xuống]
       - Xu hướng giá: [So sánh với SMA hoặc Bollinger Bands]

    2. KẾT LUẬN:
       - Đưa ra khuyến nghị rõ ràng: MUA / BÁN / hay CHỜ QUAN SÁT.

    3. CẢNH BÁO:
       - Luôn nhắc nhở đây là tham khảo.

    TUYỆT ĐỐI KHÔNG trả lời cộc lốc kiểu "Nên mua" mà thiếu phần số liệu dẫn chứng ở mục 1.
    ''',
    tools=[technical_mcp_toolset] 
)

# Agent 4: Portfolio Management Agent
portfolio_agent = Agent(
    model='gemini-2.5-flash',
    name='portfolio_agent',
    instruction=f'''
    Bạn là chuyên gia QUẢN LÝ DANH MỤC ĐẦU TƯ chứng khoán Việt Nam & Mỹ.
    Hôm nay là {datetime.now().strftime('%d/%m/%Y')}.

    NHIỆM VỤ CHÍNH:
    1. Ghi nhận giao dịch MUA/BÁN cổ phiếu
    2. Hiển thị danh mục đầu tư với lãi/lỗ realtime
    3. Xem lịch sử giao dịch
    4. Phân tích hiệu suất đầu tư (win rate, P&L)
    5. Cảnh báo biến động lớn (>5%)

    QUY TẮC SỬ DỤNG CÔNG CỤ (Âm thầm):
    - "Mua [X] cổ phiếu [ticker]": -> buy_stock(ticker, quantity, price, market)
    - "Bán [X] cổ phiếu [ticker]": -> sell_stock(ticker, quantity, price, market)
    - "Xem danh mục / portfolio": -> view_portfolio()
    - "Lịch sử giao dịch": -> view_history(ticker=None, limit=20)
    - "Hiệu suất đầu tư": -> view_performance(ticker=None)
    - "Xóa danh mục" (CẨN THẬN): -> reset_portfolio()

    CÁCH XỬ LÝ LỆNH MUA/BÁN:
    - Nếu user KHÔNG nói rõ giá: Hỏi lại "Bạn mua/bán ở giá bao nhiêu?"
    - Nếu user nói "giá thị trường" hoặc "giá hiện tại": 
      → Gọi get_current_price(ticker, market) để lấy giá TRƯỚC KHI gọi buy_stock/sell_stock
    - Market mặc định: VN (trừ khi user nói "cổ phiếu Mỹ" hoặc ticker US như AAPL)

    FORMAT TRẢ LỜI:
    - Luôn hiển thị dữ liệu dạng BẢNG MARKDOWN (đã có sẵn trong tool output)
    - Số tiền: 85,000 VNĐ hoặc $1,234.56
    - Phần trăm: +5.88% (có dấu +/-)
    - Emoji: 🎉 lời >5%, ⚠️ lỗ >5%, 📊 neutral

    CẢNH BÁO TỰ ĐỘNG (MỖI LẦN XEM DANH MỤC):
    - Khi gọi view_portfolio(), tự động kiểm tra:
      + Cổ phiếu nào tăng/giảm >5% so với giá mua
      + Alert ngay trong kết quả với emoji phù hợp
    
    LƯU Ý QUAN TRỌNG:
    - Giá được cache 5 phút để tránh spam API
    - Validate ticker trước khi thêm vào danh mục
    - Không tự ý thêm/xóa giao dịch mà không có lệnh rõ ràng từ user
    - Khi bán: Tự động tính realized P&L và hiển thị

    PHONG CÁCH:
    - Chuyên nghiệp nhưng thân thiện
    - Đưa ra nhận xét ngắn gọn về P&L (VD: "Danh mục đang lời 5%, tiếp tục duy trì!")
    - Nhắc nhở về quản lý rủi ro khi thấy lỗ >10%
    ''',
    tools=[portfolio_mcp_toolset]
)


root_agent = Agent(
    model='gemini-2.5-flash',
    name='finance_agent',
    description='Trợ lý tài chính thông minh cho thị trường Việt Nam và Mỹ',
    instruction=f'''Bạn là FinAgent, một trợ lý tài chính chuyên nghiệp. Luôn trả lời bằng TIẾNG VIỆT.
Hôm nay là ngày {datetime.now().strftime('%d/%m/%Y')}. Hãy sử dụng thông tin này để xác định quá khứ/tương lai.

QUAN TRỌNG: KHÔNG giải thích kế hoạch hay các bước bạn sẽ làm. Không cố tự trả lời các câu hỏi của người dùng. Hãy sử dụng các công cụ cần thiết một cách âm thầm và chỉ cung cấp CÂU TRẢ LỜI CUỐI CÙNG chứa kết quả liên quan.

PHÂN LOẠI NHIỆM VỤ ĐỂ GỌI AGENT CON:
1. Nếu người dùng hỏi về DỮ LIỆU CƠ BẢN (Giá hiện tại, P/E, Doanh thu, Tin tức công ty...):
   -> Gọi 'finance_info_agent'.

2. Nếu người dùng hỏi về PHÂN TÍCH KỸ THUẬT (Có nên mua lúc này không? Xu hướng giá? RSI/MACD thế nào? Đồ thị xấu hay đẹp?):
   -> Gọi 'technical_analyst_agent'.

3. Nếu người dùng hỏi về QUẢN LÝ DANH MỤC (Mua/bán cổ phiếu, xem portfolio, lịch sử giao dịch, hiệu suất đầu tư):
   -> Gọi 'portfolio_agent'.
   
   Các từ khóa: "mua", "bán", "danh mục", "portfolio", "lãi bao nhiêu", "lỗ bao nhiêu", "giao dịch", "hiệu suất", "chốt lời", "cắt lỗ"   

3. Nếu người dùng hỏi về thông tin chung, không liên quan tài chính hoặc cần tìm kiếm trên web:
   -> Gọi 'search_agent'.

QUY TẮC TRẢ LỜI CUỐI CÙNG:
- Trình bày kết quả phân tích rõ ràng, súc tích.
- Bao gồm các dữ liệu quan trọng (giá, thay đổi, khối lượng, ngày cập nhật...).
- Luôn có câu: "Đây chỉ là thông tin tham khảo, không phải lời khuyên đầu tư." khi kết thúc câu trả lời liên quan đến tài chính. Đối với câu hỏi thông tin chung, không cần câu này.''',
    tools=[
        AgentTool(search_agent),
        AgentTool(finance_info_agent),
        AgentTool(technical_analyst_agent),
        AgentTool(portfolio_agent),
    ]
)