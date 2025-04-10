# 使用Python 3.11作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装Node.js (用于高德地图MCP服务器)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY mcp-client/ /app/mcp-client/
COPY amap-mcp/ /app/amap-mcp/
COPY requirements.txt /app/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

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
