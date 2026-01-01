#!/usr/bin/env python3
"""
OpenAI格式API反代服务器
将请求转发到目标API并返回流式响应
"""

import asyncio
import json
import logging
from typing import AsyncGenerator
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="OpenAI API Proxy", version="1.0.0")

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局配置
CONFIG = {}


def load_config():
    """从config.txt加载配置"""
    config_file = Path(__file__).parent / "config.txt"
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_file}")

    config = {}
    with open(config_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()

    logger.info(f"配置加载成功: API_URL={config.get('API_URL')}, PORT={config.get('PORT')}")
    return config


async def stream_response(target_url: str, headers: dict, payload: dict) -> AsyncGenerator[str, None]:
    """
    流式转发请求到目标API
    """
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                target_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"目标API返回错误: {response.status_code} - {error_text.decode()}")
                    yield f"data: {json.dumps({'error': f'API错误: {response.status_code}'})}\n\n"
                    return

                # 逐行读取SSE流
                async for line in response.aiter_lines():
                    if line.strip():
                        # 转发SSE数据
                        if line.startswith("data: "):
                            yield f"{line}\n\n"
                        else:
                            yield f"data: {line}\n\n"

    except httpx.TimeoutException:
        logger.error("请求超时")
        yield f"data: {json.dumps({'error': '请求超时'})}\n\n"
    except Exception as e:
        logger.error(f"流式请求异常: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI兼容的聊天完成接口
    """
    try:
        # 解析请求体
        body = await request.json()
        logger.info(f"收到请求: model={body.get('model')}, messages数量={len(body.get('messages', []))}")

        # 构建目标API的请求头
        headers = {
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "authorization": f"Bearer {body.get('api_key', 'Missing Key')}",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "cookie": CONFIG.get('COOKIE', ''),
            "origin": "https://chat-ai.academiccloud.de",
            "referer": "https://chat-ai.academiccloud.de/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        # 构建请求载荷（保持OpenAI格式）
        payload = {
            "model": body.get("model", "deepseek-r1"),
            "messages": body.get("messages", []),
            "temperature": body.get("temperature", 0.5),
            "top_p": body.get("top_p", 0.5),
            "stream": body.get("stream", True),
            "stream_options": body.get("stream_options", {"include_usage": True})
        }

        # 如果请求流式响应
        if payload.get("stream", True):
            return StreamingResponse(
                stream_response(CONFIG['API_URL'], headers, payload),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # 非流式响应
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    CONFIG['API_URL'],
                    headers=headers,
                    json=payload
                )
                return response.json()

    except json.JSONDecodeError:
        logger.error("请求体JSON解析失败")
        raise HTTPException(status_code=400, detail="无效的JSON格式")
    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """健康检查接口"""
    return {
        "status": "running",
        "service": "OpenAI API Proxy",
        "target": CONFIG.get('API_URL', 'Not configured')
    }


@app.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "object": "list",
        "data": [
            {
                "id": "deepseek-r1",
                "object": "model",
                "created": 1677610602,
                "owned_by": "deepseek"
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn

    # 加载配置
    CONFIG = load_config()
    port = int(CONFIG.get('PORT', 8000))

    logger.info(f"启动服务器，监听端口: {port}")
    logger.info(f"目标API: {CONFIG['API_URL']}")
    logger.info(f"访问地址: http://localhost:{port}")
    logger.info(f"OpenAI兼容接口: http://localhost:{port}/v1/chat/completions")

    # 启动服务器
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
