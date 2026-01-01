#!/usr/bin/env python3
"""
OpenAI格式API反代服务器
将请求转发到目标API并返回流式响应
使用API Key传递配置信息（cookie和目标API地址）
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, Tuple
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="OpenAI API Proxy", version="2.0.0")

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 默认配置
DEFAULT_API_URL = "https://chat-ai.academiccloud.de/api/chat/completions"
DEFAULT_MODELS_URL = "https://chat-ai.academiccloud.de/models"


def parse_api_key(api_key: str) -> Tuple[str, str, str]:
    """
    解析API Key获取配置信息
    格式: cookie|api_url 或 cookie|api_url|models_url
    如果只提供cookie，则使用默认API地址
    """
    if not api_key:
        raise ValueError("API Key不能为空")

    parts = api_key.split('|')

    if len(parts) == 1:
        # 只有cookie，使用默认API地址
        return parts[0], DEFAULT_API_URL, DEFAULT_MODELS_URL
    elif len(parts) == 2:
        # cookie和api_url
        cookie, api_url = parts
        # 从api_url推导models_url
        if '/api/chat/completions' in api_url:
            base_url = api_url.replace('/api/chat/completions', '')
            models_url = f"{base_url}/models"
        else:
            models_url = DEFAULT_MODELS_URL
        return cookie, api_url, models_url
    elif len(parts) >= 3:
        # cookie, api_url和models_url都提供
        return parts[0], parts[1], parts[2]
    else:
        raise ValueError("API Key格式错误")


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
async def chat_completions(request: Request, authorization: Optional[str] = Header(None)):
    """
    OpenAI兼容的聊天完成接口
    使用Authorization header传递配置: Bearer cookie|api_url
    """
    try:
        # 获取API Key
        api_key = None
        if authorization:
            if authorization.startswith("Bearer "):
                api_key = authorization[7:]
            else:
                api_key = authorization

        if not api_key:
            raise HTTPException(status_code=401, detail="缺少Authorization header")

        # 解析API Key获取配置
        try:
            cookie, api_url, _ = parse_api_key(api_key)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"API Key格式错误: {str(e)}")

        # 解析请求体
        body = await request.json()
        logger.info(f"收到请求: model={body.get('model')}, messages数量={len(body.get('messages', []))}")

        # 构建目标API的请求头
        headers = {
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "authorization": "Bearer Missing Key",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "cookie": cookie,
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
                stream_response(api_url, headers, payload),
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
                    api_url,
                    headers=headers,
                    json=payload
                )
                return response.json()

    except json.JSONDecodeError:
        logger.error("请求体JSON解析失败")
        raise HTTPException(status_code=400, detail="无效的JSON格式")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """健康检查接口"""
    return {
        "status": "running",
        "service": "OpenAI API Proxy",
        "version": "2.0.0",
        "usage": "使用Authorization header传递配置: Bearer cookie|api_url"
    }


@app.get("/v1/models")
async def list_models(authorization: Optional[str] = Header(None)):
    """列出可用模型 - 从目标API动态获取"""
    try:
        # 获取API Key
        api_key = None
        if authorization:
            if authorization.startswith("Bearer "):
                api_key = authorization[7:]
            else:
                api_key = authorization

        if not api_key:
            raise HTTPException(status_code=401, detail="缺少Authorization header")

        # 解析API Key获取配置
        try:
            cookie, _, models_url = parse_api_key(api_key)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"API Key格式错误: {str(e)}")

        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cookie": cookie,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(models_url, headers=headers)

            if response.status_code == 200:
                data = response.json()

                # 转换为OpenAI格式
                openai_models = []
                for model in data.get("data", []):
                    openai_model = {
                        "id": model.get("id"),
                        "object": "model",
                        "created": model.get("created", 1677610602),
                        "owned_by": model.get("owned_by", "chat-ai")
                    }
                    openai_models.append(openai_model)

                return {
                    "object": "list",
                    "data": openai_models
                }
            else:
                logger.error(f"获取模型列表失败: {response.status_code}")
                # 返回默认模型列表
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型列表异常: {str(e)}", exc_info=True)
        # 返回默认模型列表
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
    import sys

    # 从命令行参数获取端口，默认8000
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.warning(f"无效的端口号: {sys.argv[1]}, 使用默认端口8000")

    logger.info(f"启动服务器，监听端口: {port}")
    logger.info(f"访问地址: http://localhost:{port}")
    logger.info(f"OpenAI兼容接口: http://localhost:{port}/v1/chat/completions")
    logger.info(f"使用方法: 在Authorization header中传递 'Bearer cookie|api_url'")
    logger.info(f"示例: Authorization: Bearer mod_auth_openidc_session=xxx|https://chat-ai.academiccloud.de/api/chat/completions")

    # 启动服务器
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
