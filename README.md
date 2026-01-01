# OpenAI API 反代服务器

将目标API反代为OpenAI格式的接口，支持流式响应。

## 文件说明

- `proxy_server.py` - 主服务器脚本
- `config.txt` - 配置文件
- `test_client.py` - 测试客户端
- `requirements.txt` - Python依赖包

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置服务

编辑 `config.txt` 文件，修改以下配置：

```
# API配置文件
# 目标API地址
API_URL=https://chat-ai.academiccloud.de/api/chat/completions

# Cookie (必需 - 从浏览器获取)
COOKIE=mod_auth_openidc_session=你的cookie值

# 本地服务端口
PORT=8000
```

**重要**: 请从浏览器开发者工具中获取最新的Cookie值并更新到配置文件中。

### 3. 启动服务器

```bash
python proxy_server.py
```

服务器将在后台运行，监听配置的端口（默认8000）。

### 4. 测试服务

```bash
python test_client.py
```

## API接口

### 聊天完成接口

**端点**: `POST http://localhost:8000/v1/chat/completions`

**请求示例**:

```json
{
  "model": "deepseek-r1",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你好"}
  ],
  "temperature": 0.5,
  "top_p": 0.5,
  "stream": true,
  "stream_options": {"include_usage": true}
}
```

**响应格式**: Server-Sent Events (SSE) 流式响应

### 模型列表接口

**端点**: `GET http://localhost:8000/v1/models`

### 健康检查接口

**端点**: `GET http://localhost:8000/`

## 使用示例

### Python客户端

```python
import httpx
import json

url = "http://localhost:8000/v1/chat/completions"

payload = {
    "model": "deepseek-r1",
    "messages": [
        {"role": "user", "content": "你好"}
    ],
    "stream": True
}

with httpx.Client() as client:
    with client.stream("POST", url, json=payload) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data != "[DONE]":
                    print(json.loads(data))
```

### curl命令

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-r1",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="dummy",  # 可以是任意值
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="deepseek-r1",
    messages=[
        {"role": "user", "content": "你好"}
    ],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## 后台运行

### Windows

使用 `pythonw` 在后台运行：

```bash
pythonw proxy_server.py
```

或创建批处理文件 `start_server.bat`:

```batch
@echo off
start /B pythonw proxy_server.py
echo 服务器已在后台启动
```

### Linux/Mac

使用 `nohup` 在后台运行：

```bash
nohup python proxy_server.py > server.log 2>&1 &
```

查看日志：

```bash
tail -f server.log
```

停止服务：

```bash
ps aux | grep proxy_server.py
kill <进程ID>
```

## 注意事项

1. **Cookie有效期**: Cookie可能会过期，如果出现认证错误，请更新config.txt中的Cookie值
2. **端口占用**: 如果8000端口被占用，请修改config.txt中的PORT配置
3. **网络连接**: 确保服务器能够访问目标API地址
4. **流式响应**: 默认启用流式响应，适合实时对话场景

## 故障排查

### 连接失败

- 检查目标API地址是否正确
- 检查网络连接
- 验证Cookie是否有效

### 认证错误

- 从浏览器开发者工具获取最新的Cookie
- 更新config.txt中的COOKIE配置

### 端口被占用

- 修改config.txt中的PORT为其他端口
- 或停止占用该端口的其他程序

## 许可证

MIT License
