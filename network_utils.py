import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from math import ceil
from typing import Any, Optional, Union, Type

import requests

from config import REPLY_RULE, MAX_ALLOWED_LATENCY_SECONDS, TEST_DATA, REQUEST_HEADERS


class ReturnStatus(Enum):
    """业务逻辑状态枚举类。

    定义了不同的响应内容类型和处理状态。

    :cvar SUCCESS: 处理成功。
    :cvar CONTENT_IS_CLOUDFLARE: 响应内容为 Cloudflare 页面。
    :cvar UNEXPECTED_CONTENT: 其他类型的响应内容。
    :cvar INVALID_CONTENT: JSON 响应但包含未预期内容。
    :cvar SERVER_ERROR_50X: 50x 服务器错误。
    :cvar TIME_OUT: 请求超时。
    :cvar REQUEST_FAIL: 请求失败。
    :cvar ERROR: 处理错误。
    """

    SUCCESS = auto()  # 处理成功
    CONTENT_IS_CLOUDFLARE = auto()  # 响应内容为 Cloudflare 页面
    UNEXPECTED_CONTENT = auto()  # 其他类型的响应内容
    INVALID_CONTENT = auto()  # JSON响应但包含未预期内容
    SERVER_ERROR_50X = auto()  # 50x 服务器错误
    TIME_OUT = auto()  # 请求超时
    REQUEST_FAIL = auto()  # 请求失败
    ERROR = auto()  # 处理错误

    def __str__(self) -> str:
        """返回枚举值的字符串表示。"""
        return self.name

    @classmethod
    def from_string(cls, status_str: str) -> Type["ReturnStatus"]:
        """从字符串获取对应的状态枚举值。

        :param status_str: 状态字符串
        :returns: 对应的状态枚举值，如果不存在返回 None
        """
        try:
            return cls[status_str.upper()]
        except KeyError:
            return Type[cls.ERROR]


@dataclass
class ProcessedResponse:
    """处理后的响应数据类。

    用于封装 HTTP 响应或业务处理的结果数据。

    :param status: HTTP状态码或业务状态
    :param data: 响应数据内容
    :param latency: 处理延迟时间(秒)
    :param timestamp: 响应处理时间戳
    """

    status: Union[ReturnStatus, str, int]
    data: Any = field(default=None)
    latency: float = field(default=0.0)
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """数据类初始化后的处理。

        - 确保 status 为字符串类型
        """
        # 转换状态码为字符串
        if isinstance(self.status, (int, Enum)):
            self.status = str(self.status)

    def to_dict(self) -> dict[str, Any]:
        """将响应数据转换为字典格式。

        :returns: 包含响应数据的字典
        """
        return {
            "status": self.status,
            "data": self.data,
            "latency": self.latency,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessedResponse":
        """从字典创建响应对象。

        :param data: 包含响应数据的字典
        :returns: 新响应对象实例
        """
        timestamp = (
            datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now()
        )
        return cls(
            status=data.get("status", ""),
            data=data.get("data"),
            latency=float(data.get("latency", 0.0)),
            timestamp=timestamp,
        )


def parse_response_data(response: requests.Response) -> Optional[str]:
    """解析响应对象中的 JSON 数据并提取 "data" 字段。

    :param response: 包含 JSON 数据的响应对象。
    :return: 如果解析成功，返回 "data" 字段的值；否则返回 None。
    """
    try:
        return response.json().get("data", "")
    except (ValueError, AttributeError):
        return None


def check_cloudflare_block(response_text: str) -> bool:
    """检查响应文本是否包含 Cloudflare 拦截信息。

    :param response_text: 响应文本内容。
    :return: 如果包含 Cloudflare 拦截信息，返回 True；否则返回 False。
    """
    return any(
        cf_word in response_text for cf_word in ["Attention Required!", "Cloudflare"]
    )


def validate_response_content(
    response_data: str, rules: dict[str, Union[list[str], str]]
) -> bool:
    """验证响应内容是否符合预设规则。

    :param response_data: 需要验证的响应数据。
    :param rules: 包含验证规则的字典，如 "include_words" 和 "fail_regex"。
    :return: 如果响应内容符合规则，返回 True；否则返回 False。
    """
    include_words = rules.get("include_words", [])
    fail_regex = rules.get("fail_regex", "")

    if not all(word in response_data for word in include_words):
        return False

    if re.search(fail_regex, response_data):
        return False

    return True


def process_successful_response(
    url: str,
    response: requests.Response,
    latency: float,
    rules: dict[str, Union[list[str], str]],
) -> ProcessedResponse:
    """处理 HTTP 请求的成功响应，验证响应内容是否符合预设规则。

    :param url: 请求的目标 URL。
    :param response: 成功响应对象。
    :param latency: 请求的延迟时间，以秒为单位。
    :param rules: 包含检查响应内容的规则的字典。
    :return: 包含状态、数据和延迟的 `ProcessedResponse` 对象。
    """
    response_data = parse_response_data(response)

    if response_data is None:
        if check_cloudflare_block(response.text):
            logging.error(f"Failed to get response from {url} because of Cloudflare.")
            return ProcessedResponse(
                status=ReturnStatus.CONTENT_IS_CLOUDFLARE,
                data="Cloudflare block",
                latency=latency,
            )
        else:
            logging.error(f"Failed to parse JSON response from {url}.")
        return ProcessedResponse(
            status=ReturnStatus.UNEXPECTED_CONTENT,
            data="Failed to parse JSON",
            latency=latency,
        )

    if validate_response_content(response_data, rules):
        logging.info(f"Successful response from {url}. Latency: {latency:.2f}s")
        return ProcessedResponse(
            status=ReturnStatus.SUCCESS, data=response_data, latency=latency
        )
    else:
        logging.error(f"Invalid response content from {url}: {response_data[15:]}")
        return ProcessedResponse(
            status=ReturnStatus.INVALID_CONTENT,
            data=response_data,
            latency=latency,
        )


def handle_error_response(
    url: str, status_code: int, latency: float
) -> ProcessedResponse:
    """处理非 200 的 HTTP 响应状态码。

    :param url: 请求的目标 URL。
    :param status_code: HTTP 响应状态码。
    :param latency: 请求的延迟时间，以秒为单位。
    :return: 包含状态、数据和延迟的 `ProcessedResponse` 对象。
    """
    if 500 <= status_code < 600:
        logging.warning(f"Server error ({status_code}) at {url}.")
        return ProcessedResponse(
            status=ReturnStatus.SERVER_ERROR_50X,
            data=f"HTTP error {status_code} at {url}",
            latency=latency,
        )
    elif status_code == 429:
        logging.warning(f"Rate limit exceeded (429) at {url}.")
        return ProcessedResponse(
            status=status_code,
            data=f"Rate limit exceeded (429) at {url}.",
            latency=latency,
        )
    elif status_code == 401:
        logging.warning(f"Unauthorized (401) at {url}.")
        return ProcessedResponse(
            status=status_code,
            data=f"Unauthorized (401) at {url}.",
            latency=latency,
        )
    else:
        logging.warning(f"Unhandled HTTP status code ({status_code}) at {url}.")
        return ProcessedResponse(
            status=ReturnStatus.ERROR,
            data=f"Unhandled HTTP status code {status_code} at {url}.",
            latency=latency,
        )


def make_request(
    url: str, test_data: dict, rules: dict[str, Union[list[str], str]], verify: bool
) -> ProcessedResponse:
    """发起 HTTP POST 请求，并根据响应状态码和延迟返回结果。

    :param url: 请求的目标 URL。
    :param test_data: 包含请求数据的字典。
    :param rules: 应用于响应的规则。
    :param verify: 指定是否验证 HTTPS 证书。
    :return: 如果请求成功，返回包含 URL、延迟信息的字典；如果遇到错误（如超时、服务器错误等），则返回错误代码的字符串。
    :raises TypeError: 如果输入参数类型不正确。
    :raises ValueError: 如果输入参数值无效。
    """
    try:
        start_time = time.time()
        timeout = MAX_ALLOWED_LATENCY_SECONDS + max(
            1, ceil(MAX_ALLOWED_LATENCY_SECONDS / 3)
        )
        response = requests.post(
            url,
            json=test_data,
            headers=REQUEST_HEADERS,
            timeout=timeout,
            verify=verify,
        )
        latency = time.time() - start_time

        # 检查 latency 的合理性
        if latency < 0 or latency > MAX_ALLOWED_LATENCY_SECONDS:
            logging.warning(f"Unrealistic latency detected: {latency}s for URL: {url}")
            latency = -1  # 使用 -1 表示异常

        # 成功响应的处理
        if response.status_code == 200:
            return process_successful_response(url, response, latency, rules)

        # 失败响应的选项
        return handle_error_response(url, response.status_code, latency)

    except requests.exceptions.Timeout:
        logging.debug(f"Timeout accessing {url}.")
        return ProcessedResponse(
            status=ReturnStatus.TIME_OUT,
            data=f"Timeout accessing {url}.",
            latency=-1,
        )
    except requests.exceptions.RequestException as e:
        logging.debug(f"Request to {url} failed: {e}")
        return ProcessedResponse(
            status=ReturnStatus.REQUEST_FAIL,
            data=f"Request to {url} failed.",
            latency=-1,
        )


def check_endpoint(
    url: str,
    test_data: dict = TEST_DATA,
    rules: dict[str, Union[list[str], str]] = REPLY_RULE,
) -> tuple[str, ProcessedResponse]:
    """检查给定的 URL 是否可用，支持 HTTP 和 HTTPS 协议。

    :param url: 要检查的基础 URL
    :param test_data: 请求中发送的数据，默认使用 TEST_DATA
    :param rules: 响应的验证规则，默认使用 REPLY_RULE

    :raises RequestException: 当请求发生网络错误时
    :raises ValueError: 当响应不符合预期规则时
    """
    verify = url.startswith("https://")
    url_response = make_request(url, test_data, rules, verify=verify)
    return url, url_response


if __name__ == "__main__":
    pass
