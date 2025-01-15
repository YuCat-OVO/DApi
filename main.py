import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from typing import Union

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
from network_utils import check_endpoint
from url_utils import generate_urls

setup_logger()


# Suppress InsecureRequestWarning globally
urllib3.disable_warnings(InsecureRequestWarning)


def categorize_result(
    url: str,
    response: Union[str, dict[str, Union[str, float]]],
    categorized_results: dict[str, Union[dict[str, float], list[str]]],
) -> None:
    """
    根据结果分类 URL。

    Args:
        response: Union[str, dict[str, Union[str, float]]]: 检查结果。
        url (str): 当前 URL。
        categorized_results (dict): 分类结果字典。
    """
    status = response.get("status", "failed")

    if status == "success":
        protocol_cate = (
            "available_https_endpoints"
            if url.startswith("https://")
            else "available_http_endpoints"
        )
        categorized_results[protocol_cate][url] = response.get("latency")
    elif status == "429":
        categorized_results["rate_limited"][url] = response.get("latency")
    elif status == "50x":
        categorized_results["service_unavailable"][url] = response.get("latency")
    elif status == "timeout":
        categorized_results["timeout_or_unreachable"].append(url)
    elif status == "401":
        categorized_results["unauthorized_urls"].append(url)
    else:
        categorized_results["failed_urls"].append(url)


def process_urls_with_thread_pool(
    urls: list[str],
    categorized_results: dict[str, Union[dict[str, float], list[str]]],
    max_workers: int = URL_PROCESSING_MAX_PROCESSES,
    show_progress: bool = SHOW_SSL_PROGRESS_BAR,
) -> None:
    """
    Process URL tasks using a thread pool.

    Args:
        urls (list[str]): List of URLs to check.
        categorized_results (Optional[dict]): Dictionary to store categorized results.
        max_workers (int): Maximum number of worker threads.
        show_progress (bool): Whether to display a progress bar.
    """
    # Initialize the ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        # 初始化进度条
        progress_bar = (
            tqdm(total=len(urls), desc="Checking APIs") if show_progress else None
        )

        for url in urls:
            futures.append(executor.submit(check_endpoint, url, TEST_DATA, REPLY_RULE))

        for future in as_completed(futures):
            result = future.result()
            url, response = result
            if result:
                categorize_result(url, response, categorized_results)
            if progress_bar:
                progress_bar.update(1)

        # 关闭进度条
        if progress_bar:
            progress_bar.close()


def display_results(
    categorized_results: dict[str, Union[dict[str, float], list[str]]],
    show_list: bool = False,
    sort_results: bool = True,
) -> None:
    """
    显示分类结果。

    Args:
        categorized_results (dict): 包含所有分类结果的字典。
        show_list (bool): 是否输出纯净的 URL 列表（无延迟和 Emoji）。
        sort_results (bool): 是否按延迟排序，默认按延迟排序（仅对 "available_endpoints" 的数据生效）。
    """

    def print_urls(title: str, url_dict: dict[str, float], emoji: str) -> None:
        """打印分类 URL 列表（支持排序和延迟显示）。"""
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

    # 打印 HTTPS 和 HTTP 的端点
    print_urls(
        "HTTPS Endpoints",
        categorized_results.get("available_https_endpoints"),
        "\U0001F512",  # 🔐
    )
    print_urls(
        "HTTP Endpoints",
        categorized_results.get("available_http_endpoints"),
        "\U0001F310",  # 🌐
    )

    # 打印受限制的 URL
    print_urls(
        "Rate Limited URLs",
        categorized_results.get("rate_limited"),
        "\U0001F6AB",  # 🚫
    )

    # 打印50x URL
    print_urls(
        "Service Unavailable URLs",
        categorized_results.get("service_unavailable"),
        "\U0001F6AB",  # 🚫
    )

    # 分类汇总
    if not show_list:
        print("\n\U0001F4CA Summary of Results:")  # 📊
        for category, data in categorized_results.items():
            if isinstance(data, dict):  # 处理字典类型的数据
                print(f"  - {category.replace('_', ' ').title()}: {len(data)} URLs")
            elif isinstance(data, list):  # 处理列表类型的数据
                print(f"  - {category.replace('_', ' ').title()}: {len(data)} URLs")


def main():
    """
    主函数，执行 URL 检查和结果保存工作。

    """
    # 加载 URL 和初始数据
    urls = generate_urls()
    if not urls:
        logging.error("No URLs to check. Exiting.")
        return

    if SAVE_PROCESSED_DATA:
        with open("processed_urls.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(urls))

    # 初始化分类结果字典
    categorized_results = {
        "available_https_endpoints": {},
        "available_http_endpoints": {},
        "rate_limited": {},
        "service_unavailable": {},
        "timeout_or_unreachable": [],
        "unauthorized_urls": [],
        "failed_urls": [],
    }

    # 使用线程池检查 URL
    process_urls_with_thread_pool(urls, categorized_results)

    # 打印分类结果
    display_results(categorized_results)

    if SAVE_PROCESSED_DATA:
        # 对 HTTPS 端点进行排序后保存
        https_sorted = sorted(
            categorized_results.get("available_https_endpoints", {}).items(),
            key=lambda item: item[1],  # 按延迟值排序
        )
        with open("https_urls.txt", "w", encoding="utf-8") as f:
            for url, latency in https_sorted:
                f.write(f"{url} (Latency: {latency})\n")

        # 对 HTTP 端点进行排序后保存
        http_sorted = sorted(
            categorized_results.get("available_http_endpoints", {}).items(),
            key=lambda item: item[1],  # 按延迟值排序
        )
        with open("http_urls.txt", "w", encoding="utf-8") as f:
            for url, latency in http_sorted:
                f.write(f"{url} (Latency: {latency})\n")

        rate_limit = sorted(categorized_results.get("rat"))


if __name__ == "__main__":
    main()
