#!/usr/bin/env python3
"""
测试OpenAI API代理服务器
"""

import httpx
import json
import sys


def test_stream_chat():
    """测试流式聊天接口"""
    url = "http://localhost:8000/v1/chat/completions"

    payload = {
        "model": "deepseek-r1",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        "temperature": 0.5,
        "top_p": 0.5,
        "stream": True,
        "stream_options": {"include_usage": True}
    }

    print("发送请求到代理服务器...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")

    try:
        with httpx.Client(timeout=300.0) as client:
            with client.stream("POST", url, json=payload) as response:
                print(f"响应状态码: {response.status_code}\n")

                if response.status_code != 200:
                    print(f"错误: {response.text}")
                    return

                print("接收流式响应:\n" + "=" * 50)

                for line in response.iter_lines():
                    if line.strip():
                        print(line)

                        # 解析并显示内容
                        if line.startswith("data: "):
                            data_str = line[6:]  # 去掉 "data: " 前缀
                            if data_str == "[DONE]":
                                print("\n" + "=" * 50)
                                print("流式响应完成")
                                break

                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        print(content, end="", flush=True)
                            except json.JSONDecodeError:
                                pass

    except httpx.ConnectError:
        print("错误: 无法连接到服务器，请确保代理服务器正在运行")
        print("运行命令: python proxy_server.py")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)


def test_health_check():
    """测试健康检查接口"""
    url = "http://localhost:8000/"

    try:
        response = httpx.get(url, timeout=10.0)
        print(f"健康检查: {response.status_code}")
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        print(f"健康检查失败: {str(e)}")
        return False


def test_models():
    """测试模型列表接口"""
    url = "http://localhost:8000/v1/models"

    try:
        response = httpx.get(url, timeout=10.0)
        print(f"\n可用模型: {response.status_code}")
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"获取模型列表失败: {str(e)}")


if __name__ == "__main__":
    print("OpenAI API代理服务器测试\n")

    # 测试健康检查
    if not test_health_check():
        sys.exit(1)

    # 测试模型列表.txt
    test_models()

    # 测试流式聊天
    print("\n" + "=" * 50)
    print("测试流式聊天接口")
    print("=" * 50 + "\n")
    test_stream_chat()
