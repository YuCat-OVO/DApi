import logging
import re
import time
from dataclasses import dataclass
from math import ceil
from typing import Union

import requests

from config import REPLY_RULE, MAX_ALLOWED_LATENCY_SECONDS, TEST_DATA, REQUEST_HEADERS


@dataclass
class ProcessedResponse:
    status: str
    data: str
    latency: float


def process_successful_response(
    url: str,
    response: requests.Response,
    latency: float,
    rules: dict[str, Union[list[str], str]],
) -> dict[str, Union[str, float]]:
    """
    处理 HTTP 请求的成功响应，验证响应内容是否符合预设规则。

    参数:
        url (str): 请求的目标 URL。
        response (requests.Response): 成功的响应对象。
        latency (float): 请求的延迟时间，以秒为单位。
        rules (dict[str, Union[list[str], str]]): 包含检查响应内容的规则的字典。

    返回:
        dict[str, Union[str, float]]: 包含状态、数据和延迟的字典。
    """
    try:
        response_data = response.json().get("data", "")
    except (ValueError, AttributeError):
        if any(
            cf_word in response.text
            for cf_word in ["Attention Required!", "Cloudflare"]
        ):
            logging.error(f"Failed to get response from {url} because of Cloudflare.")
        else:
            logging.error(f"Failed to parse JSON response from {url}.")
        return {"status": "error", "data": "Failed to parse JSON", "latency": latency}

    if all(word in response_data for word in rules.get("include_words", [])):
        if re.search(rules.get("fail_regex", ""), response_data):
            logging.debug(f"Invalid response content from {url}: {response_data}")
            return {
                "status": "invalid_content",
                "data": response_data,
                "latency": latency,
            }

        logging.info(f"Successful response from {url}. Latency: {latency:.2f}s")
        return {
            "status": "success",
            "data": response_data,
            "latency": latency,
        }

    logging.debug(f"Unexpected response content from {url}: {response_data}")
    return {"status": "unexpected_content", "data": response_data, "latency": latency}


def handle_error_response(
    url: str, status_code: int, latency: float
) -> dict[str, Union[str, float]]:
    """
    处理非 200 的 HTTP 响应状态码。

    参数:
        url (str): 请求的目标 URL。
        status_code (int): HTTP 响应状态码。
        latency (float): 请求的延迟时间。

    返回:
        dict[str, Union[str, float]]: 包含状态、数据和延迟的字典。
    """
    if 500 <= status_code < 600:
        logging.warning(f"Server error ({status_code}) at {url}.")
        return {
            "status": "50x",
            "data": f"HTTP error {status_code} at {url}",
            "latency": latency,
        }
    if status_code == 429:
        logging.warning(f"Rate limit exceeded (429) at {url}.")
        return {
            "status": "429",
            "data": f"Rate limit exceeded (429) at {url}.",
            "latency": latency,
        }
    if status_code == 401:
        logging.warning(f"Unauthorized (401) at {url}.")
        return {
            "status": "401",
            "data": f"Unauthorized (401) at {url}.",
            "latency": latency,
        }

    logging.warning(f"Unhandled HTTP status code ({status_code}) at {url}.")
    return {
        "status": str(status_code),
        "data": f"Unhandled HTTP status code {status_code} at {url}.",
        "latency": latency,
    }


def make_request(
    url: str, test_data: dict, rules: dict[str, Union[list[str], str]], verify: bool
) -> dict[str, Union[str, float]]:
    """
    发起 HTTP POST 请求，并根据响应状态码和延迟返回结果。

    参数:
        url (str): 请求的目标 URL。
        test_data (dict): 包含请求数据的字典。
        rules (dict[str, list[str]]): 应用于响应的规则。
        verify (bool): 指定是否验证 HTTPS 证书。

    返回:
        dict[str, Union[str, float]]: 如果请求成功，返回包含 URL、延迟信息的字典；
        如果遇到错误（如超时、服务器错误等），则返回错误代码的字符串。
    """
    try:
        start_time = time.time()
        response = requests.post(
            url,
            json=test_data,
            headers=REQUEST_HEADERS,
            timeout=(
                MAX_ALLOWED_LATENCY_SECONDS + 1
                if ceil(MAX_ALLOWED_LATENCY_SECONDS / 3) <= 0
                else MAX_ALLOWED_LATENCY_SECONDS + ceil(MAX_ALLOWED_LATENCY_SECONDS / 3)
            ),
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
        return {
            "status": "timeout",
            "data": f"Timeout accessing {url}.",
            "latency": -1,
        }
    except requests.exceptions.RequestException:
        logging.debug(f"Request to {url} failed.")
        return {
            "status": "failed",
            "data": f"Request to {url} failed.",
            "latency": -1,
        }


def generate_urls(url: str) -> tuple[str, str]:
    """
    根据输入的 URL 生成相应的 HTTP 和 HTTPS URL，并适当调整端口号。

    参数:
        url (str): 输入的 URL。

    返回:
        tuple[str, str]: 包含 HTTP 和 HTTPS URL 的元组。

    抛出:
        ValueError: 如果输入的 URL 格式不正确。

    注意:
        本函数假设输入的 URL 格式正确，并以 "http://" 或 "https://" 开头。
        函数会检查并替换标准端口号：80 (HTTP) 和 443 (HTTPS)。
    """
    if not url.startswith(("http://", "https://")):
        logging.error(f"Invalid URL format: {url}")
        raise ValueError(f"Invalid URL: {url}")

    # 根据协议生成对应的 URL
    http_url = (
        url.replace("https://", "http://", 1) if url.startswith("https://") else url
    )
    https_url = (
        url.replace("http://", "https://", 1) if url.startswith("http://") else url
    )

    # 替换标准端口号
    http_url = http_url.replace(":443/", ":80/", 1) if ":443/" in http_url else http_url
    https_url = (
        https_url.replace(":80/", ":443/", 1) if ":80/" in https_url else https_url
    )

    return http_url, https_url


def check_endpoint(
    url: str,
    test_data: dict = TEST_DATA,
    rules: dict[str, Union[list[str], str]] = REPLY_RULE,
) -> dict[str, tuple[str, dict[str, Union[str, float]]]]:
    """
    检查给定的 URL 是否可用，支持 HTTP 和 HTTPS 协议。

    参数:
        url (str): 要检查的基础 URL。
        test_data (dict): 请求中发送的数据。
        rules (dict[str, Union[list[str], str]]): 响应的验证规则。

    返回:
        tuple[str, dict[str, Union[str, float]]]: 包含成功的 URL 和其延迟信息的字典；
        如果失败，返回失败信息。
    """
    http_url, https_url = generate_urls(url)

    url_response = {
        "http": (
            url,
            {
                "status": "failed",
                "data": f"Request to {url} failed: No valid response from HTTP",
                "latency": -1,
            },
        ),
        "https": (
            url,
            {
                "status": "failed",
                "data": f"Request to {url} failed: No valid response from HTTPS",
                "latency": -1,
            },
        ),
    }

    # 检查 HTTP URL
    http_response = make_request(http_url, test_data, rules, verify=False)
    if http_response["status"]:
        url_response["http"] = (http_url, http_response)

    # 检查 HTTPS URL
    https_response = make_request(https_url, test_data, rules, verify=True)
    if https_response["status"]:
        url_response["https"] = (https_url, https_response)

    return url_response


if __name__ == "__main__":
    pass
