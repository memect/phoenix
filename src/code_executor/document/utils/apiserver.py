"""API Server 交互模块

封装与 memect API 服务器的交互逻辑。
"""

import io
import time
import zipfile
from typing import Any

import requests


class ApiServer:
    """API Server 操作类"""

    def __init__(
        self,
        base_url: str = "http://localhost:6111/api",
        poll_interval: float = 1.0,
    ):
        """初始化 API Server 客户端
        
        Args:
            base_url: API 服务器基础 URL
            poll_interval: 异步轮询间隔（秒）
        """
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.session = requests.Session()

    def invoke(
        self,
        name: str,
        data: bytes,
        params: dict[str, str] | None = None,
        output_format: str = "json",
        async_: bool = False,
    ) -> dict[str, Any] | None:
        """调用 API
        
        Args:
            name: API 名称，如 pdf2doc
            data: 请求数据（PDF 文件内容）
            params: 额外参数
            output_format: 输出格式，json 或 zip
            async_: 是否使用异步模式
            
        Returns:
            API 返回的 JSON 数据
            
        Raises:
            Exception: API 调用失败
        """
        url = f"{self.base_url}/{name}"
        query = params.copy() if params else {}
        query["async"] = "true" if async_ else "false"
        query["output-format"] = output_format

        response = self.session.post(url, data=data, params=query)

        if response.status_code == 200:
            return self._get_result(name, response, output_format, async_)
        elif response.status_code == 400:
            error = response.json().get("error", {})
            raise Exception(f"API 调用失败: {error}")
        else:
            raise Exception(
                f"API 调用失败: status_code={response.status_code}, "
                f"response={response.text[:200]}"
            )

    def _get_result(
        self,
        name: str,
        response: requests.Response,
        output_format: str,
        async_: bool,
    ) -> dict[str, Any] | None:
        """获取 API 结果
        
        Args:
            name: API 名称
            response: 初始响应
            output_format: 输出格式
            async_: 是否异步模式
            
        Returns:
            API 返回的数据
        """
        if not async_:
            return self._save_result(response, output_format)

        # 异步模式：轮询获取结果
        data = response.json()
        task_id = data["task"]["id"]
        url = f"{self.base_url}/{name}"

        while True:
            poll_response = self.session.get(url, params={"task_id": task_id})

            if poll_response.status_code == 200:
                return self._save_result(poll_response, output_format)
            elif poll_response.status_code == 400:
                result = poll_response.json()
                error = result.get("error", {})
                code = error.get("code", "")

                if code == "error":
                    raise Exception(f"API 执行失败: {error}")
                elif code in ("running", "waiting"):
                    time.sleep(self.poll_interval)
                else:
                    raise Exception(f"API 调用失败: {error}")
            else:
                raise Exception(
                    f"API 调用失败: status_code={poll_response.status_code}"
                )

    def _save_result(
        self, response: requests.Response, output_format: str
    ) -> dict[str, Any] | None:
        """解析响应结果
        
        Args:
            response: HTTP 响应
            output_format: 输出格式
            
        Returns:
            解析后的数据
        """
        if output_format == "json":
            return response.json()
        elif output_format == "zip":
            with io.BytesIO(response.content) as fp:
                with zipfile.ZipFile(fp) as zf:
                    # 返回 zip 文件内容列表
                    return {"files": zf.namelist()}
        else:
            raise ValueError(f"不支持的输出格式: {output_format}")
