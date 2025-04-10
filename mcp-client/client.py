import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        # 初始化火山云OpenAI客户端
        self.client = OpenAI(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key="670307c4-3342-4582-a8e9-5680b764fd28"
        )

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        # 显示思考过程 - 更详细的输出
        final_text = [
            "### 正在分析您的需求...", 
            "我正在仔细分析您的旅游需求，提取关键信息如下：\n\n"
            "1. 目的地信息：您想去哪个城市或景区旅游\n"
            "2. 旅行时间：您计划的旅行天数和时间段\n"
            "3. 出行偏好：您喜欢的景点类型、美食和住宿偏好\n"
            "4. 特殊需求：如家庭出行、商务旅行等\n\n"
            "我将基于这些信息，结合实时天气和交通数据，为您定制最适合的旅游路线。"
        ]

        response = await self.session.list_tools()
        available_tools = [{ 
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        # 初始化火山云API调用
        formatted_tools = []
        for tool in available_tools:
            formatted_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"]
                }
            }
            formatted_tools.append(formatted_tool)
        
        final_text.append("### 思考中...")    
        final_text.append("我正在判断需要查询哪些信息来帮助您规划旅程。我将使用高德地图API获取以下数据：\n\n"
                         "1. 天气数据：查询目的地的天气预报，包括温度、降水和风力\n"
                         "2. 交通信息：获取不同景点之间的路线规划和交通方式\n"
                         "3. 景点数据：搜索目的地的热门景点、美食和住宿\n"
                         "4. 地理信息：将地址转换为经纬度坐标，以便进行距离计算\n\n"
                         "这些数据将帮助我为您创建一个合理、高效的旅游行程。")
        response = self.client.chat.completions.create(
            model="ep-20250318134029-b5xwx",
            max_tokens=1000,
            messages=messages,
            tools=formatted_tools
        )

        # 处理火山云API响应
        choice = response.choices[0]
        if choice.message.content:
            final_text.append(f"### AI初步分析")  
            final_text.append(choice.message.content)
            final_text.append("")
            
        if choice.message.tool_calls:
            final_text.append(f"### 正在查询相关数据")  
            for tool_call in choice.message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                # 将JSON字符串转换为字典
                import json
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError as e:
                    final_text.append(f"[Error parsing tool arguments: {e}]")
                    continue
                
                # 根据工具类型显示不同的描述
                tool_descriptions = {
                    "maps_weather": f"**正在查询{tool_args.get('city', '')}的天气信息...**",
                    "maps_geo": f"**正在将地址'{tool_args.get('address', '')}'转换为经纬度坐标...**",
                    "maps_regeocode": f"**正在将坐标'{tool_args.get('location', '')}'转换为地址信息...**",
                    "maps_text_search": f"**正在搜索关键词'{tool_args.get('keywords', '')}'的地点信息...**",
                    "maps_around_search": f"**正在搜索坐标'{tool_args.get('location', '')}'附近的地点...**",
                    "maps_direction_walking": f"**正在规划从'{tool_args.get('origin', '')}'到'{tool_args.get('destination', '')}'的步行路线...**",
                    "maps_direction_driving": f"**正在规划从'{tool_args.get('origin', '')}'到'{tool_args.get('destination', '')}'的驾车路线...**",
                    "maps_direction_transit_integrated": f"**正在规划从'{tool_args.get('origin', '')}'到'{tool_args.get('destination', '')}'的公交路线...**"
                }
                
                description = tool_descriptions.get(tool_name, f"**正在调用{tool_name}工具...**")
                final_text.append(description)
                
                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # 将工具调用结果添加到对话上下文
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args)
                        }
                    }]
                })
                
                # 确保工具调用结果是字符串
                result_content = result.content
                if not isinstance(result_content, str):
                    result_content = str(result_content)
                
                messages.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id,
                    "content": result_content
                })
                
                # 显示数据分析过程 - 更详细的输出
                final_text.append(f"### 数据分析中...")
                final_text.append(f"我已经获取了相关数据，正在进行深入分析：\n\n"
                                 f"1. 天气数据分析：根据获取的天气信息，我正在判断最适合的游览时间和室内/室外活动安排\n"
                                 f"2. 路线优化：根据交通数据，我正在计算最佳的景点游览顺序，减少交通时间\n"
                                 f"3. 景点筛选：根据您的偏好和时间限制，我正在选择最适合的景点组合\n"
                                 f"4. 用餐安排：我正在结合您的美食偏好和行程安排，选择适合的用餐地点\n"
                                 f"5. 住宿推荐：根据您的偏好和行程安排，我正在选择最佳的住宿位置\n\n"
                                 f"我将综合这些分析结果，为您生成一个个性化、高效的旅游行程。")

                # 获取下一个响应
                response = self.client.chat.completions.create(
                    model="ep-20250318134029-b5xwx",
                    max_tokens=1000,
                    messages=messages,
                )

                if response.choices[0].message.content:
                    final_text.append("### 生成最终结果")
                    final_text.append(response.choices[0].message.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="MCP Client for 智能旅游规划助手")
    parser.add_argument("server_path", help="Path to the MCP server script")
    parser.add_argument("--list-tools", action="store_true", help="List available tools and exit")
    parser.add_argument("--query", type=str, help="Process a single query and exit")
    
    # 确保在没有足够参数时不会崩溃
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    client = MCPClient()
    try:
        await client.connect_to_server(args.server_path)
        
        if args.list_tools:
            # 只列出工具并退出
            # 已经在connect_to_server中列出了工具
            return
        elif args.query:
            # 处理单个查询并退出
            response = await client.process_query(args.query)
            print(response)
        else:
            # 交互式聊天模式
            await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())