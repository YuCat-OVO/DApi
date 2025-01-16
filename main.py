import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, fields
from typing import Union, Dict, List, Type

import urllib3
from tqdm import tqdm
from urllib3.exceptions import InsecureRequestWarning

from config import (
    URL_PROCESSING_MAX_PROCESSES,
    SHOW_SSL_PROGRESS_BAR,
    TEST_DATA,
    REPLY_RULE,
    SAVE_PROCESSED_DATA,
)
from logging_utils import setup_logger
from network_utils import check_endpoint, ProcessedResponse, ReturnStatus
from url_utils import generate_urls

setup_logger()


# Suppress InsecureRequestWarning globally
urllib3.disable_warnings(InsecureRequestWarning)


@dataclass
class CategorizedResults:
    """存储所有 URL 的分类结果。

    :param available_https_endpoints: 可用的 HTTPS 端点及其延迟。
    :param available_http_endpoints: 可用的 HTTP 端点及其延迟。
    :param rate_limited: 被限流的端点及其延迟。
    :param cloudflare_blocked: 被 Cloudflare 拦截的端点及其延迟。
    :param service_unavailable: 服务不可用的端点及其延迟。
    :param unauthorized_urls: 未授权的 URL 列表。
    :param timeout_or_unreachable: 超时或无法访问的 URL 列表。
    :param failed_urls: 检查失败的 URL 列表。
    """

    available_https_endpoints: Dict[str, float] = field(default_factory=dict)
    available_http_endpoints: Dict[str, float] = field(default_factory=dict)
    rate_limited: Dict[str, float] = field(default_factory=dict)
    cloudflare_blocked: Dict[str, float] = field(default_factory=dict)
    service_unavailable: Dict[str, float] = field(default_factory=dict)
    unauthorized_urls: Dict[str, float] = field(default_factory=dict)
    timeout_or_unreachable: List[str] = field(default_factory=list)
    failed_urls: List[str] = field(default_factory=list)

    def add_result(self, url: str, response: ProcessedResponse) -> None:
        """根据响应结果将 URL 分类到相应的类别中。

        :param url: 检查的 URL。
        :param response: 处理后的响应对象。
        """
        match response.status:
            case ReturnStatus.SUCCESS:
                if url.startswith("https://"):
                    self.available_https_endpoints[url] = response.latency
                else:
                    self.available_http_endpoints[url] = response.latency
            case "429":
                self.rate_limited[url] = response.latency
            case ReturnStatus.CONTENT_IS_CLOUDFLARE:
                self.cloudflare_blocked[url] = response.latency
            case ReturnStatus.SERVER_ERROR_50X:
                self.service_unavailable[url] = response.latency
            case "401":
                self.unauthorized_urls[url] = response.latency
            case ReturnStatus.TIME_OUT:
                self.timeout_or_unreachable.append(url)
            case ReturnStatus.REQUEST_FAIL:
                self.failed_urls.append(url)
            case ReturnStatus.ERROR:
                self.failed_urls.append(url)
            case _:
                self.failed_urls.append(url)

    def to_dict(self) -> Dict[str, Union[Dict[str, float], List[str]]]:
        """将分类结果转换为字典格式。

        :returns: 包含所有分类结果的字典。
        """
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def sort(self, field_name: str, reverse: bool = False) -> None:
        """对指定字段进行排序。

        :param field_name: 需要排序的字段名称。
        :param reverse: 是否降序排序，默认为升序。
        :raises ValueError: 如果字段名称无效或字段不支持排序。
        """
        if not hasattr(self, field_name):
            raise ValueError(f"Field '{field_name}' does not exist")

        field_value = getattr(self, field_name)

        if isinstance(field_value, dict):
            # Sort dictionary by value, handling -1 latency
            sorted_items = sorted(
                field_value.items(),
                key=lambda x: float("inf") if x[1] == -1 else x[1],
                reverse=reverse,
            )
            setattr(self, field_name, dict(sorted_items))
        elif isinstance(field_value, list):
            # Sort list
            field_value.sort(reverse=reverse)
        else:
            raise ValueError(f"Field '{field_name}' is not sortable")


def process_urls_with_thread_pool(
    urls: list[str],
    categorized_results: Type[CategorizedResults],
    max_workers: int = URL_PROCESSING_MAX_PROCESSES,
    show_progress: bool = SHOW_SSL_PROGRESS_BAR,
) -> None:
    """
    使用线程池处理 URL 任务。

    :param urls: 需要检查的 URL 列表。
    :param categorized_results: 存储分类结果的对象。
    :param max_workers: 最大线程数。
    :param show_progress: 是否显示进度条。
    """
    # 初始化线程池
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(check_endpoint, url, TEST_DATA, REPLY_RULE) for url in urls
        ]
        # 初始化进度条
        progress_bar = (
            tqdm(total=len(urls), desc="Checking APIs") if show_progress else None
        )
        for future in as_completed(futures):
            result = future.result()
            url, response = result
            if result:
                categorized_results.add_result(url, response)
            if progress_bar:
                progress_bar.update(1)

        # 关闭进度条
        if progress_bar:
            progress_bar.close()


def display_results(categorized_results, show_list=False, sort_results=True):
    """
    显示分类结果。

    :param categorized_results: 包含所有分类结果的对象。
    :param show_list: 是否输出纯净的 URL 列表（无延迟和 Emoji）。
    :param sort_results: 是否按延迟排序，默认按延迟排序（仅对 "available_endpoints" 的数据生效）。
    """

    def print_urls(title, url_dict, emoji):
        """打印分类 URL 列表（支持排序和延迟显示）。

        :param title: 分类标题。
        :param url_dict: 包含 URL 和延迟的字典。
        :param emoji: 分类的 Emoji 图标。
        """
        print(f"\n{emoji} {title}:")
        urls = list(url_dict.keys())
        if sort_results:
            urls = sorted(urls, key=lambda this_url: url_dict[this_url])
        for url in urls:
            latency = url_dict[url]
            latency_display = (
                "Timeout" if latency == float("inf") else f"{latency:.2f} ms"
            )
            print(f"{emoji} {url} (Latency: {latency_display})")

    # 使用更符合场景的 Emoji
    print_urls(
        "HTTPS Endpoints", categorized_results.available_https_endpoints, "\U0001F511"
    )  # 🔑
    print_urls(
        "HTTP Endpoints", categorized_results.available_http_endpoints, "\U0001F310"
    )  # 🌐
    print_urls(
        "Rate Limited URLs", categorized_results.rate_limited, "\U0001F6A7"
    )  # 🚧
    print_urls(
        "Cloudflare Blocked URLs", categorized_results.cloudflare_blocked, "\U0001F6E1"
    )  # 🛡️
    print_urls(
        "Service Unavailable URLs",
        categorized_results.service_unavailable,
        "\U0001F6A8",
    )  # 🚨
    print_urls(
        "Unauthorized URLs", categorized_results.unauthorized_urls, "\U0001F510"
    )  # 🔐
    print_urls(
        "Timeout or Unreachable URLs",
        categorized_results.timeout_or_unreachable,
        "\U0001F504",
    )  # 🔄
    print_urls("Failed URLs", categorized_results.failed_urls, "\U0001F6AB")  # 🚫

    if not show_list:
        print("\n\U0001F4CA Summary of Results:")  # 📊
        for category, data in categorized_results.to_dict().items():
            if isinstance(data, dict):
                print(f"  - {category.replace('_', ' ').title()}: {len(data)} URLs")
            elif isinstance(data, list):
                print(f"  - {category.replace('_', ' ').title()}: {len(data)} URLs")


def main():
    """
    主函数，执行 URL 检查和结果保存工作。

    1. 加载 URL 列表。
    2. 如果启用了保存功能，将 URL 列表保存到文件。
    3. 初始化分类结果对象。
    4. 使用线程池检查 URL 并将结果分类。
    5. 打印分类结果。
    6. 如果启用了保存功能，将分类结果保存到文件。
    """
    # 加载 URL 列表
    urls = generate_urls()
    if not urls:
        logging.error("No URLs to check. Exiting.")
        return

    # 如果启用了保存功能，将 URL 列表保存到文件
    if SAVE_PROCESSED_DATA:
        try:
            with open("processed_urls.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(urls))
            logging.info("URL list saved to processed_urls.txt")
        except IOError as e:
            logging.error(f"Failed to save URL list: {e}")

    # 初始化分类结果对象
    categorized_results = CategorizedResults()

    # 使用线程池检查 URL 并将结果分类
    try:
        process_urls_with_thread_pool(urls, categorized_results)
    except Exception as e:
        logging.error(f"Error during URL checking: {e}")
        return

    # 打印分类结果
    display_results(categorized_results)

    # 如果启用了保存功能，将分类结果保存到文件
    if SAVE_PROCESSED_DATA:
        try:
            with open("categorized_results.json", "w", encoding="utf-8") as f:
                import json

                json.dump(categorized_results.to_dict(), f, indent=4)
            logging.info("Categorized results saved to categorized_results.json")
        except IOError as e:
            logging.error(f"Failed to save categorized results: {e}")


if __name__ == "__main__":
    main()
