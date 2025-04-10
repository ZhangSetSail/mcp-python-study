import streamlit as st
import asyncio
import os
import sys
import json
import subprocess
import time
from threading import Thread
from queue import Queue

# 设置页面配置
st.set_page_config(
    page_title="智能旅游规划助手",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 添加简化的打字机效果函数
def typewriter_effect(text, container, speed=0.05, steps=10):
    """实现打字机效果的函数
    
    Args:
        text: 要显示的文本
        container: Streamlit容器
        speed: 每步的延迟时间
        steps: 分多少步显示
    """
    # 确保文本不为空
    if not text or len(text) == 0:
        container.markdown(text, unsafe_allow_html=True)
        return
        
    # 分多步显示
    chunk_size = max(1, len(text) // steps)
    
    # 逐步显示文本
    for i in range(0, len(text), chunk_size):
        end = min(i + chunk_size, len(text))
        container.markdown(text[:end], unsafe_allow_html=True)
        time.sleep(speed)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #FF4785;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .tool-name {
        font-weight: bold;
        color: #FF4785;
    }
    .tool-desc {
        color: #666;
        font-style: italic;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #f0f2f6;
        border-left: 5px solid #FF4785;
    }
    .assistant-message {
        background-color: #f8f9fa;
        border-left: 5px solid #4285F4;
    }
    .tool-call {
        background-color: #f0f8ff;
        border-left: 5px solid #34A853;
        font-family: monospace;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
    }
    .thinking-section {
        background-color: #fff8e1;
        border-left: 5px solid #FFC107;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
    }
    .thinking-header {
        font-weight: bold;
        color: #FF8F00;
        margin-bottom: 0.3rem;
    }
    .data-analysis {
        background-color: #e8f5e9;
        border-left: 5px solid #4CAF50;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
    }
    .final-result {
        background-color: #e3f2fd;
        border-left: 5px solid #2196F3;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.3rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 初始化会话状态
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'connected' not in st.session_state:
    st.session_state.connected = False

if 'available_tools' not in st.session_state:
    st.session_state.available_tools = []
    
if 'process' not in st.session_state:
    st.session_state.process = None

# 主标题
st.markdown("<h1 class='main-header'>智能旅游规划助手</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>结合高德地图API，为您提供个性化旅游规划</p>", unsafe_allow_html=True)

# 侧边栏 - 连接设置
with st.sidebar:
    st.header("🔌 连接设置")
    
    # 设置API密钥
    amap_api_key = st.text_input(
        "高德地图API密钥", 
        value=os.environ.get("AMAP_MAPS_API_KEY", "66297b6685c934c7e48df4f6891091f3"),
        type="password"
    )
    
    # 设置MCP服务器路径
    mcp_server_path = st.text_input(
        "MCP服务器路径", 
        value="/app/amap-mcp/amap-maps-mcp-server.js"
    )
    
    # 连接按钮
    if st.button("连接到MCP服务器"):
        with st.spinner("正在连接到MCP服务器..."):
            # 设置环境变量
            os.environ["AMAP_MAPS_API_KEY"] = amap_api_key
            
            try:
                # 直接运行命令行版本的客户端，但不等待用户输入
                # 确保环境变量正确设置
                env_vars = os.environ.copy()
                env_vars["AMAP_MAPS_API_KEY"] = amap_api_key
                
                cmd = ["python", "client.py", mcp_server_path, "--list-tools"]
                result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars)
                
                if result.returncode != 0:
                    raise Exception(f"命令执行失败: {result.stderr}")
                
                # 解析输出获取工具列表
                output = result.stdout
                if "Connected to server with tools:" in output:
                    tools_line = output.split("Connected to server with tools:")[1].strip()
                    tools_list = eval(tools_line)  # 安全地解析工具列表
                    
                    # 创建工具对象列表
                    class Tool:
                        def __init__(self, name):
                            self.name = name
                            self.description = self._get_description(name)
                            
                        def _get_description(self, name):
                            descriptions = {
                                "maps_regeocode": "将一个高德经纬度坐标转换为行政区划地址信息",
                                "maps_geo": "将详细的结构化地址转换为经纬度坐标",
                                "maps_ip_location": "IP 定位根据用户输入的 IP 地址，定位 IP 的所在位置",
                                "maps_weather": "根据城市名称或者标准adcode查询指定城市的天气",
                                "maps_search_detail": "POI详情查询",
                                "maps_bicycling": "骑行路径规划",
                                "maps_direction_walking": "步行路径规划",
                                "maps_direction_driving": "驾车路径规划",
                                "maps_direction_transit_integrated": "公交路径规划",
                                "maps_distance": "距离测量",
                                "maps_text_search": "关键词搜索",
                                "maps_around_search": "周边搜索"
                            }
                            return descriptions.get(name, "无描述信息")
                    
                    st.session_state.available_tools = [Tool(name) for name in tools_list]
                    st.session_state.connected = True
                    
                    st.success(f"成功连接到MCP服务器！可用工具: {len(st.session_state.available_tools)}个")
                else:
                    raise Exception("无法解析工具列表")
                    
            except Exception as e:
                st.error(f"连接失败: {str(e)}")
    
    # 如果已连接，显示可用工具
    if st.session_state.connected:
        st.header("🛠️ 可用工具")
        for tool in st.session_state.available_tools:
            with st.expander(f"{tool.name}"):
                st.markdown(f"<p class='tool-desc'>{tool.description}</p>", unsafe_allow_html=True)

# 主界面 - 聊天
if not st.session_state.connected:
    st.info("请先连接到MCP服务器")
else:
    # 显示历史消息
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"<div class='chat-message user-message'>{message['content']}</div>", unsafe_allow_html=True)
        elif message["role"] == "assistant":
            content = message["content"]
            # 处理工具调用标记
            if "[Calling tool" in content:
                parts = content.split("[Calling tool")
                main_content = parts[0]
                tool_calls = ["[Calling tool" + part for part in parts[1:]]
                
                st.markdown(f"<div class='chat-message assistant-message'>{main_content}", unsafe_allow_html=True)
                for tool_call in tool_calls:
                    st.markdown(f"<div class='tool-call'>{tool_call}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-message assistant-message'>{content}</div>", unsafe_allow_html=True)
    
    # 用户输入
    user_input = st.chat_input("输入您的旅游需求...")
    
    if user_input:
        # 添加用户消息到历史
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.markdown(f"<div class='chat-message user-message'>{user_input}</div>", unsafe_allow_html=True)
        
        # 处理用户输入
        with st.spinner("AI正在思考..."):
            try:
                # 直接运行命令行版本的客户端处理查询
                # 确保环境变量正确设置
                env_vars = os.environ.copy()
                env_vars["AMAP_MAPS_API_KEY"] = amap_api_key
                
                cmd = ["python", "client.py", mcp_server_path, "--query", user_input]
                result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars)
                
                if result.returncode != 0:
                    raise Exception(f"命令执行失败: {result.stderr}")
                
                # 获取输出作为响应
                response = result.stdout
                if "Query:" in response and "\n" in response:
                    # 提取实际响应内容（去除命令行提示符）
                    response = response.split("Query:")[1].split("\n", 1)[1].strip()
                
                # 添加助手消息到历史
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 显示响应
                content = response
                
                # 创建一个容器来存放整个消息
                message_container = st.container()
                
                with message_container:
                    # 消息开始标记
                    st.markdown("<div class='chat-message assistant-message'>", unsafe_allow_html=True)
                    
                    # 简化内容处理逻辑
                    if "[Calling tool" in content:
                        parts = content.split("[Calling tool")
                        main_content = parts[0]
                        tool_calls = ["[Calling tool" + part for part in parts[1:]]
                        
                        # 创建思考过程容器
                        thinking_container = st.empty()
                        
                        # 使用纯 Python 打字机效果
                        formatted_content = f"<div class='thinking-section'><div class='thinking-header'>智能助手分析</div>{main_content}</div>"
                        typewriter_effect(formatted_content, thinking_container, speed=0.1, steps=5)
                        
                        # 展示工具调用
                        for tool_call in tool_calls:
                            tool_container = st.empty()
                            tool_formatted = f"<div class='tool-call'>{tool_call}</div>"
                            typewriter_effect(tool_formatted, tool_container, speed=0.1, steps=3)
                    else:
                        # 如果没有工具调用，直接显示内容
                        result_container = st.empty()
                        formatted_result = f"<div class='final-result'>{content}</div>"
                        typewriter_effect(formatted_result, result_container, speed=0.1, steps=5)
                    
                    # 消息结束标记
                    st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"处理失败: {str(e)}")

# 页脚
st.markdown("---")
st.markdown("© 2025 智能旅游规划助手 | 基于高德地图API和火山云AI")

# 运行应用的主函数
if __name__ == "__main__":
    # Streamlit已经处理了主循环，无需额外代码
    pass
