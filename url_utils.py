import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from tqdm import tqdm

from config import (
    FILE_PRIORITY,
    SHOW_SSL_PROGRESS_BAR,
    SSL_CERT_CHECK_MAX_WORKERS,
    PROCESS_CERTIFICATE,
)
from ssl_utils import get_domains_from_cert
from url_class import ApiURL


def deduplicate_urls(url_list: list[ApiURL]) -> list[ApiURL]:
    """使用字典对具有相同 host 的 ApiURL 类列表进行去重和合并。

    ApiURL 类的相等性是基于其 host 属性。

    :param url_list: 包含 ApiURL 实例的列表
    :return: 去重并合并后的 ApiURL 实例列表
    """

    # 创建字典，键是 host，值是对应的 ApiURL 实例列表
    host_to_urls = {}
    for url in url_list:
        if url.host in host_to_urls:
            host_to_urls[url.host].append(url)
        else:
            host_to_urls[url.host] = [url]

    # 遍历字典的值，合并相同 host 的 ApiURL 实例
    merged_url_list = []
    for url_list_in_host in host_to_urls.values():
        merged_url = url_list_in_host[0]
        for url in url_list_in_host[1:]:
            merged_url += url
        merged_url_list.append(merged_url)

    return merged_url_list


def load_urls_from_file(file_priority: Optional[list[str]] = None) -> list[ApiURL]:
    """自动加载文件中的 URL，优先按照文件列表顺序读取，标准化 URL 并去重后返回。

    :param file_priority: 指定文件优先级列表，默认为配置中的 FILE_PRIORITY。
    :return: 包含有效且标准化的 URL 列表。
    """
    # 动态处理默认值
    if file_priority is None:
        file_priority = FILE_PRIORITY

    urls_list = []

    for file_path in file_priority:
        if os.path.exists(file_path):
            logging.info(f"Loading URLs from file: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    for line_number, line in enumerate(file, start=1):
                        try:
                            urls_list.append(ApiURL.from_url(line))
                        except Exception as e:
                            logging.warning(
                                f"Failed to load URL at line {line_number}: {line.strip()}. Error: {e}"
                            )
                break
            except (PermissionError, IOError) as e:
                logging.error(f"Failed to read file {file_path}: {e}")

    urls_list = deduplicate_urls(urls_list)

    if not urls_list:
        logging.error(
            f"No valid URLs found - either files {file_priority} don't exist or contain no valid URLs"
        )
        return []

    logging.info(f"Loaded {len(urls_list)} unique URLs.")
    return urls_list  # 不排序，按需调整


def fetch_and_normalize_url_list(
    raw_url_list: list[ApiURL], show_progress: bool = True
) -> list[ApiURL] | None:
    """生成一个 URL 列表，所有 URL 统一存储，并对 IP 类型的 URL 进行证书获取域名处理。

    :param raw_url_list: 原始 URL 列表。
    :param show_progress: 是否显示进度条，默认开启。
    :return: 包含所有处理后的 URL 的列表，IP URL 会保留，同时添加解析出的域名 URL。
    """
    process_url_list = raw_url_list.copy()
    # 创建线程池执行多线程任务
    with ThreadPoolExecutor(max_workers=SSL_CERT_CHECK_MAX_WORKERS) as executor:
        future_to_url: dict = {}

        # 筛选 IP URL
        ip_url_list = [ip_url for ip_url in process_url_list if not ip_url.has_domain]

        # 初始化进度条
        progress_bar: Optional[tqdm] = (
            tqdm(total=len(ip_url_list), desc="Processing IP URLs")
            if show_progress
            else None
        )

        # 提交任务
        for url in ip_url_list:
            for port in url.port_set:
                future = executor.submit(get_domains_from_cert, url.host, port)
                future_to_url[future] = url

        # 收集解析结果
        to_add = []
        for future in as_completed(future_to_url):
            original_url = future_to_url[future]
            try:
                domain_list = future.result()
                if domain_list:
                    for domain in domain_list:
                        try:
                            new_url = ApiURL.replace_domain(original_url, domain)
                        except ValueError as e:
                            logging.info(f"Error replacing domain: {e}")
                        else:
                            if new_url is not None:
                                to_add.append(new_url)
                    logging.info(
                        f"Found {len(domain_list)} domains for {original_url.host},{domain_list}"
                    )
            except Exception as e:
                logging.info(f"Error resolving host from {original_url.host}: {e}")
            finally:
                if progress_bar:
                    progress_bar.update(1)

        # 关闭进度条
        if progress_bar:
            progress_bar.close()

        process_url_list.extend(to_add)

    return deduplicate_urls(process_url_list)


def generate_urls(
    input_file: list[str] = FILE_PRIORITY,
    show_progress: bool = SHOW_SSL_PROGRESS_BAR,
    process_certificate: bool = PROCESS_CERTIFICATE,
) -> list[str]:
    """生成处理后的 URL 列表，并根据配置决定是否进行证书检测和域名替换。

    该函数从指定的输入文件中加载原始 URL 列表，并根据配置决定是否对 IP 类型的 URL 进行证书检测和域名替换。
    处理后的 URL 列表会进一步调用 `generate_url_list` 方法生成最终的 URL 列表，并确保去重。

    :param input_file: 输入文件路径列表，包含原始 URL 列表。默认从 `FILE_PRIORITY` 配置中读取。
    :param show_progress: 是否显示进度条。默认从 `SHOW_SSL_PROGRESS_BAR` 配置中读取。
    :param process_certificate: 是否对 IP 类型的 URL 进行证书检测和域名替换。默认从 `PROCESS_CERTIFICATE` 配置中读取。
    :return: 包含处理后的 URL 列表，已去重。
    :raises FileNotFoundError: 如果输入文件不存在或无法读取。
    :raises ValueError: 如果输入文件内容格式不正确。
    """
    # 加载 URL 列表
    raw_urls = load_urls_from_file(input_file)
    if not raw_urls:
        logging.error("No valid URLs found in the input file.")
        return []

    if process_certificate:
        # 对 IP 类型的 URL 进行证书检测和域名替换
        processed_urls = fetch_and_normalize_url_list(raw_urls, show_progress)
        added_urls_count = len(processed_urls) - len(raw_urls)
        logging.info(
            f"Generated {len(processed_urls)} processed URLs, added {added_urls_count} new URLs."
        )
    else:
        processed_urls = raw_urls
        logging.info(
            f"Returning {len(raw_urls)} raw URLs without certificate processing."
        )

    all_urls = set()
    for api_url in processed_urls:
        for url in api_url.generate_url_list():
            all_urls.add(url)

    # 去重返回最终的 URL 列表
    final_urls = list(set(all_urls))
    logging.info(f"Final URL count after adding API paths: {len(final_urls)}")
    return final_urls


if __name__ == "__main__":
    pass
