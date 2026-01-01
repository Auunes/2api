# 使用官方Python镜像作为基础
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制当前目录下的所有文件到工作目录
COPY proxy_server.py .

# 安装依赖
RUN pip install --no-cache-dir fastapi httpx uvicorn

# 暴露端口（默认8000，可通过环境变量修改）
ENV PORT=8000
EXPOSE $PORT

# 启动命令，使用环境变量指定端口
CMD ["sh", "-c", "uvicorn proxy_server:app --host 0.0.0.0 --port $PORT"]