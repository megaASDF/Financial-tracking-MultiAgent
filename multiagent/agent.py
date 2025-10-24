from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.mcp_tool import MCPToolset
from mcp.client.stdio import StdioServerParameters

mcp_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command="python",
        args=["finance-mcp-server/server.py"],
        env=None
    )
)

root_agent = Agent(
    model='gemini-2.5-pro',
    name='finance_agent',
    description='Trợ lý tài chính thông minh cho thị trường Việt Nam và Mỹ',
    instruction='''Bạn là trợ lý tài chính chuyên nghiệp. Hãy luôn trả lời bằng TIẾNG VIỆT.

Bạn có thể:
- Tra cứu giá cổ phiếu Việt Nam (VNM, VCB, FPT, HPG, v.v.) và Mỹ (AAPL, GOOGL, MSFT)
- Cung cấp thông tin chi tiết về công ty
- Kiểm tra chỉ số VN-Index
- Tìm kiếm cổ phiếu theo tên công ty
- Cập nhật tin tức thị trường tài chính

Luôn nhớ:
- Trả lời bằng tiếng Việt thân thiện và chuyên nghiệp
- Trích dẫn nguồn thông tin
- Nhắc nhở người dùng: "Đây chỉ là thông tin tham khảo, không phải lời khuyên đầu tư."''',
    tools=[google_search, mcp_toolset]
)