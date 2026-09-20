from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
import asyncio
import json
from typing import Any

import httpx

from app.config import Settings, get_settings


class LLMProviderError(RuntimeError):
    pass


class ModelNotConfiguredError(LLMProviderError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    async def chat_stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        """以文本增量形式返回兼容 OpenAI 消息格式的回复。"""
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _endpoint(self) -> str:
        base = self.settings.ai_base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    async def chat_stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        if not (
            self.settings.ai_api_key
            and self.settings.ai_base_url
            and self.settings.ai_model
        ):
            raise ModelNotConfiguredError("尚未配置模型服务")

        payload: dict[str, Any] = {
            "model": self.settings.ai_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.2,
        }
        if tools:
            # 工具证据由受控的后端只读网关预先查询；禁止模型自行发起未审计调用。
            payload["tools"] = tools
            payload["tool_choice"] = "none"

        timeout = httpx.Timeout(connect=10, read=60, write=15, pool=10)
        headers = {
            "Authorization": f"Bearer {self.settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(3):
            emitted = False
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST", self._endpoint(), headers=headers, json=payload
                    ) as response:
                        if response.status_code >= 400:
                            detail = (await response.aread()).decode("utf-8", errors="replace")[:500]
                            raise LLMProviderError(
                                f"模型服务返回 {response.status_code}：{detail or '无错误详情'}"
                            )
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            raw = line[5:].strip()
                            if not raw or raw == "[DONE]":
                                continue
                            try:
                                chunk = json.loads(raw)
                                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                            except (json.JSONDecodeError, IndexError, AttributeError, TypeError):
                                continue
                            if content:
                                emitted = True
                                yield str(content)
                if not emitted:
                    raise LLMProviderError("模型服务未返回有效内容")
                return
            except asyncio.CancelledError:
                raise
            except (httpx.HTTPError, LLMProviderError) as exception:
                last_error = exception
                if emitted or attempt == 2:
                    break
                await asyncio.sleep(0.4 * (2 ** attempt))
        raise LLMProviderError(f"模型服务暂时不可用：{last_error}") from last_error


def get_llm_provider() -> LLMProvider:
    return OpenAICompatibleProvider(get_settings())
