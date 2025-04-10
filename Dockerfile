# 使用已经包含了curl和build-essential的镜像
FROM python:3.11

# 设置工作目录
WORKDIR /app

# 安装uv并确保它可被执行
RUN curl --proto '=https' --tlsv1.2 -LsSf https://github.com/astral-sh/uv/releases/download/0.6.14/uv-installer.sh | sh && \
    find / -name uv -type f 2>/dev/null || echo "uv not found" && \
    ls -la ~/.cargo/bin/ || echo "~/.cargo/bin/ not exists" && \
    which uv || echo "uv not in PATH"

# 直接使用pip代替uv创建虚拟环境
RUN python -m venv /app/.venv && \
    . /app/.venv/bin/activate && \
    pip install --upgrade pip && \
    pip install streamlit anthropic python-dotenv mcp

# 复制项目文件
COPY . /app/

# 设置环境变量
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"
ENV AMAP_MAPS_API_KEY=66297b6685c934c7e48df4f6891091f3

# 暴露Streamlit默认端口
EXPOSE 8501

# 启动命令
CMD ["streamlit", "run", "app.py"]
