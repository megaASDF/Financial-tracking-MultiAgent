# agent.py
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.agent_tool import AgentTool
from mcp.client.stdio import StdioServerParameters

# --- Get the absolute path to THIS script's directory (multiagent) ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# --- MODIFIED: Go UP one level, then DOWN into finance-mcp-server ---
server_script_path = os.path.join(script_dir, "..", "finance-mcp-server", "server.py")

# --- Get the absolute path to the current Python executable ---
python_executable_path = sys.executable

print("="*60)
print(f"Agent directory is: {script_dir}")
print(f"Attempting to launch MCP server at: {server_script_path}")
print(f"Using Python interpreter: {python_executable_path}")
print("="*60)

# FIXED: Increase timeout to 30 seconds for slow API calls
mcp_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command=python_executable_path,
        args=[server_script_path],
        env=None
    )
)

search_agent = Agent(
    model='gemini-2.5-flash', 
    name='search_agent',
    instruction='''You're a spealist in Google Search''',
    tools=[google_search],
)

finance_info_agent = Agent(
    model='gemini-2.5-flash',
    name='finance_info_agent',
    instruction='''You're a specialist in providing financial information about stocks, companies, and market trends.''',
    tools=[mcp_toolset]
)

root_agent = Agent(
    model='gemini-2.5-flash',
    model='gemini-2.5-flash',
    name='finance_agent',
    description='Trợ lý tài chính thông minh cho thị trường Việt Nam và Mỹ',
    instruction=f'''Bạn là FinAgent, một trợ lý tài chính chuyên nghiệp. Luôn trả lời bằng TIẾNG VIỆT.
Hôm nay là ngày {datetime.now().strftime('%d/%m/%Y')}. Hãy sử dụng thông tin này để xác định quá khứ/tương lai.

QUAN TRỌNG: KHÔNG giải thích kế hoạch hay các bước bạn sẽ làm. Hãy sử dụng các công cụ cần thiết một cách âm thầm và chỉ cung cấp CÂU TRẢ LỜI CUỐI CÙNG chứa kết quả phân tích.

Nhiệm vụ của bạn:
- Phân tích và cung cấp thông tin về cổ phiếu Việt Nam (VNM, FPT...) và Mỹ (AAPL, GOOGL...).
- Kiểm tra chỉ số VN-Index.
- Tìm kiếm cổ phiếu.
- Cập nhật tin tức thị trường.

QUY TẮC SỬ DỤNG CÔNG CỤ (Âm thầm thực hiện):
- Nếu hỏi giá HIỆN TẠI: Dùng 'get_stock_price'.
- Nếu hỏi giá trong QUÁ KHỨ (có ngày tháng, "tháng trước"...): Dùng 'get_stock_history' (định dạng YYYY-MM-DD).
- Nếu hỏi chỉ số tài chính VN (P/E, ROE...): Dùng 'get_vn_company_financials'.
- Nếu hỏi thông tin TỔNG QUAN công ty: Dùng 'get_company_overview'.
- Nếu tìm mã cổ phiếu VN: Dùng 'search_vietnamese_stocks'.
- Nếu cần tin tức: Dùng 'get_market_news'.
- Nếu cần thông tin chung KHÁC: Dùng 'google_search'.

QUY TẮC TRẢ LỜI CUỐI CÙNG:
- Trình bày kết quả phân tích rõ ràng, súc tích.
- Bao gồm các dữ liệu quan trọng (giá, thay đổi, khối lượng, ngày cập nhật...).
- Luôn có câu: "Đây chỉ là thông tin tham khảo, không phải lời khuyên đầu tư."''',
    tools=[
        google_search,
        mcp_toolset
    ]
)