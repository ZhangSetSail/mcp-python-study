# 使用Python 3.11作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装Node.js和必要的工具
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    git \
    build-essential \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY mcp-client/ /app/mcp-client/
COPY amap-mcp/ /app/amap-mcp/
COPY requirements.txt /app/
COPY pyproject.toml /app/
COPY uv.lock /app/

# 安装uv
RUN curl -sSf https://astral.sh/uv/install.sh | sh
# 确保路径正确设置
ENV PATH="/root/.cargo/bin:/root/.uv/bin:${PATH}"
# 验证uv安装
RUN ls -la /root/.cargo/bin || echo "cargo bin not found" && \
    ls -la /root/.uv/bin || echo "uv bin not found" && \
    which uv || echo "uv not in PATH"

# 使用pip安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建一个简单的MCP模块
RUN mkdir -p /app/mcp/client/stdio && \
    echo '\
class ClientSession:\n\
    async def list_tools(self):\n\
        return []\n\
\n\
class StdioServerParameters:\n\
    def __init__(self, *args, **kwargs):\n\
        pass\n\
' > /app/mcp/__init__.py && \
    echo '\
def stdio_client(*args, **kwargs):\n\
    pass\n\
' > /app/mcp/client/__init__.py && \
    echo '\
def stdio_client(*args, **kwargs):\n\
    pass\n\
' > /app/mcp/client/stdio/__init__.py && \
    touch /app/mcp/client/stdio/py.typed

# 安装高德地图MCP服务器依赖
WORKDIR /app/amap-mcp
RUN npm install

# 返回主工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露Streamlit默认端口
EXPOSE 8501

# 启动命令
CMD ["sh", "-c", "cd /app/mcp-client && python -m streamlit run app.py"]
