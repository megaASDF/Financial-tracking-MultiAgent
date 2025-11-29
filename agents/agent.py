# agent.py
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.agent_tool import AgentTool
from mcp import StdioServerParameters

# --- Get the absolute path to THIS script's directory (multiagent) ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# --- MODIFIED: Go UP one level, then DOWN into finance-mcp-server ---
server_script_path = os.path.join(script_dir, "..", "finance-mcp-server", "server.py")
technical_server_path = os.path.join(script_dir, "..", "finance-mcp-server", "technical_server.py")

# --- Get the absolute path to the current Python executable ---
python_executable_path = sys.executable

print("="*60)
print(f"Agent directory is: {script_dir}")
print(f"Attempting to launch MCP server at: {server_script_path}")
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

# Create Agents
search_agent = Agent(
    model='gemini-2.5-flash', 
    name='search_agent',
    instruction='''You're a specialist in Google Search''',
    tools=[google_search],
)

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
    ]
)