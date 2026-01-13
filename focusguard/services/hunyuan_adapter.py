"""
FocusGuard v2.0 - Tencent Hunyuan API Adapter

腾讯混元 API 适配器，提供 OpenAI 兼容接口。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class HunyuanAdapter:
    """
    腾讯混元 API 适配器。

    腾讯混元使用腾讯云的签名认证方式（TC3-HMAC-SHA256）。
    """

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        region: str = "ap-guangzhou",
        endpoint: str = "hunyuan.tencentcloudapi.com",
    ):
        """
        初始化腾讯混元适配器。

        Args:
            secret_id: 腾讯云 SecretId
            secret_key: 腾讯云 SecretKey
            region: 地域
            endpoint: API 端点
        """
        self._secret_id = secret_id
        self._secret_key = secret_key
        self._region = region
        self._endpoint = endpoint

        logger.info("HunyuanAdapter initialized")

    def _sign(
        self,
        secret_id: str,
        secret_key: str,
        endpoint: str,
        params: dict,
    ) -> tuple[str, str, str]:
        """
        生成腾讯云 API 签名。

        Args:
            secret_id: SecretId
            secret_key: SecretKey
            endpoint: API 端点
            params: 请求参数

        Returns:
            tuple: (authorization_header, timestamp, date)
        """
        # 公共参数
        service = "hunyuan"
        version = "2023-09-01"
        algorithm = "TC3-HMAC-SHA256"

        # 当前时间戳
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

        # 构造请求体
        body = json.dumps(params)

        # 1. 拼接规范请求串
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        canonical_headers = f"content-type:{ct}\nhost:{endpoint}\nx-date:{date}\n"
        signed_headers = "content-type;host;x-date"
        hashed_request_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{http_request_method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{hashed_request_payload}"
        )

        # 2. 拼接待签名字符串
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()
        string_to_sign = (
            f"{algorithm}\n"
            f"{timestamp}\n"
            f"{credential_scope}\n"
            f"{hashed_canonical_request}"
        )

        # 3. 计算签名
        def _hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _hmac_sha256(
            ("TC3" + secret_key).encode("utf-8"), date
        )
        secret_service = _hmac_sha256(secret_date, service)
        secret_signing = _hmac_sha256(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # 4. 拼接 Authorization
        authorization = (
            f"{algorithm} "
            f"Credential={secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return authorization, str(timestamp), date

    async def call_chat_completions(
        self,
        messages: list[dict],
        model: str = "hunyuan-lite",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: int = 30,
    ) -> str:
        """
        调用腾讯混元聊天 API。

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            timeout: 超时时间（秒）

        Returns:
            str: API 返回的文本内容

        Raises:
            aiohttp.ClientError: 网络错误
            asyncio.TimeoutError: 超时
        """
        # 构造请求参数
        params = {
            "Model": model,
            "Messages": messages,
            "Temperature": temperature,
            "TopP": 1.0,
        }

        # 生成签名
        authorization, timestamp, date = self._sign(
            self._secret_id, self._secret_key, self._endpoint, params
        )

        # 构造请求头
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self._endpoint,
            "X-Date": date,
            "Api": "3.0",
        }

        # 发送请求
        url = f"https://{self._endpoint}/"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=params, headers=headers, timeout=timeout
            ) as response:
                response.raise_for_status()
                data = await response.json()

                # 提取回复内容
                if "Response" in data:
                    return data["Response"]["Choices"][0]["Message"]["Content"]
                else:
                    raise ValueError(f"Unexpected response format: {data}")
