import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

import validators
from tqdm import tqdm

from config import (
    FILE_PRIORITY,
    SHOW_SSL_PROGRESS_BAR,
    SSL_CERT_CHECK_MAX_WORKERS,
    PROCESS_CERTIFICATE,
    DEFAULT_API_BASE_PATH,
    SERVICE_DEFAULT_PORT,
)
from ssl_utils import get_domains_from_cert


def normalize_url(raw_url: str) -> Optional[str]:
    """
    标准化 URL：标准化格式url以便于去重和验证。

    标准化 URL，不考虑协议（http/https），以 https 为默认协议进行验证。

    Args:
        raw_url (str): 输入的 URL 字符串。

    Returns:
        Optional[str]: 返回标准化后的 URL 或 None 如果 URL 无效。
    """
    if not raw_url:
        logging.debug("Empty URL provided.")
        return None

    raw_url = raw_url.strip()

    # 如果不以 https:// 开头，将其替换为 https://
    if raw_url.startswith("http://"):
        raw_url = f"https://{raw_url[7:]}"
    elif not raw_url.startswith("https://"):
        raw_url = f"https://{raw_url}"

    parsed_url = urlparse(raw_url)

    # 保留查询参数
    query = urlencode(parse_qs(parsed_url.query), doseq=True)

    # 路径处理,如果url后面接续了 DEFAULT_API_BASE_PATH 中没有的路径,则作为 API endpoint 处理,否则照常添加 /translate
    # 移除路径末尾的斜杠
    path = re.sub(r"/+$", "", parsed_url.path)

    # 检查路径是否为空或在允许的 API 路径列表中
    if path == "" or any(
        path == "/" + allowed.rstrip("/") for allowed in DEFAULT_API_BASE_PATH
    ):
        if not path.endswith("/translate"):
            path += "/translate"  # 添加 /translate 后缀

    # 重构 URL
    normalized_url = str(
        urlunparse((parsed_url.scheme, parsed_url.netloc, path, "", query, ""))
    )

    # 验证 URL 的有效性
    if validators.url(normalized_url):
        return normalized_url

    logging.debug(f"Invalid URL: {normalized_url}")
    return None


def load_urls(file_priority: Optional[list[str]] = None) -> list[str]:
    """
    自动加载文件中的 URL，优先按照文件列表顺序读取，标准化 URL 并去重后返回。

    Args:
        file_priority (Optional[list[str]]): 指定文件优先级列表，默认为配置中的 FILE_PRIORITY。

    Returns:
        list[str]: 包含有效且标准化的 URL 列表。
    """
    # 动态处理默认值
    if file_priority is None:
        file_priority = FILE_PRIORITY

    urls_set = set()

    for file_path in file_priority:
        if os.path.exists(file_path):
            logging.info(f"Loading URLs from file: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    for line in file:
                        try:
                            if url := normalize_url(line.strip()):
                                urls_set.add(url)
                        except Exception as e:
                            logging.warning(
                                f"Failed to normalize URL: {line.strip()}. Error: {e}"
                            )
                break
            except (PermissionError, IOError) as e:
                logging.error(f"Failed to read file {file_path}: {e}")

    if not urls_set:
        logging.error(
            f"None of the files {file_priority} were found or contain valid URLs."
        )
        return []

    logging.info(f"Loaded {len(urls_set)} unique URLs.")
    return list(urls_set)  # 不排序，按需调整


def check_domain(url: str) -> Optional[str]:
    """
    检查给定的 URL 是否包含有效的域名。如果域名无效或不存在，则返回 None。

    Args:
        url (str): 需要检查的 URL 字符串。

    Returns:
        Optional[str]: 有效的域名字符串，如果无效或不存在则返回 None。
    """
    # 解析 URL
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname

    if not hostname:
        return None

    if not validators.domain(hostname):
        return None

    return hostname


def extract_ip_and_port(
    url: str, add_service_default_port: bool = True
) -> tuple[str, list[int]]:
    """
    从 URL 中提取 IP 地址和端口号。如果未指定端口号，则默认返回 HTTPS 的默认端口号。

    Args:
        url (str): 输入的 URL 字符串。
        add_service_default_port (bool): 是否添加服务默认端口号，默认为 True。

    Returns:
        tuple[str, list[int]]: 包含 IP 地址和端口号的元组。
    """
    parsed = urlparse(url)
    ip = parsed.hostname
    port = parsed.port or 443  # 如果未指定端口，默认为 443（通常用于 HTTPS）

    ports = [port]
    if add_service_default_port:
        if port != SERVICE_DEFAULT_PORT:
            ports.append(SERVICE_DEFAULT_PORT)
        if port != 443:
            ports.append(443)

    return ip, ports


def replace_ip_with_domain(url: str, domain: str) -> str:
    """
    将 URL 中的主机部分替换为指定域名。

    Args:
    - url: str, 原始 URL。
    - host: str, 用于替换的域名。

    Returns:
    - str, 替换后的 URL。
    """
    # 解析 URL
    parsed_url = urlparse(url)

    # 构造新的 netloc，直接替换为指定的域名，并保留端口信息（如果有）
    new_netloc = f"{domain}:{parsed_url.port}" if parsed_url.port else domain

    # 构造替换后的 URL
    return str(urlunparse(parsed_url._replace(netloc=new_netloc)))


def make_url_list(raw_list: list[str], show_progress: bool = True) -> list[str]:
    """
    生成一个 URL 列表，所有 URL 统一存储，并对 IP 类型的 URL 进行证书获取域名处理。

    Args:
        raw_list (list[str]): 原始 URL 列表。
        show_progress (bool): 是否显示进度条，默认开启。

    Returns:
        list[str]: 包含所有处理后的 URL 的列表，IP URL 会保留，同时添加解析出的域名 URL(后面程序会处理回落 HTTP, 所以这边 URL 全为 HTTPS 协议)。
    """
    url_list = set()

    # 将原始 URL 添加到集合
    for raw_url in raw_list:
        url_list.add(raw_url)

    # 创建线程池执行多线程任务
    with ThreadPoolExecutor(max_workers=SSL_CERT_CHECK_MAX_WORKERS) as executor:
        future_to_url: dict = {}

        # 筛选 IP URL
        ip_urls = [ip_url for ip_url in raw_list if not check_domain(ip_url)]

        # 初始化进度条
        progress_bar = (
            tqdm(total=len(ip_urls), desc="Processing IP URLs")
            if show_progress
            else None
        )

        # 提交任务
        for url in ip_urls:
            ip, ports = extract_ip_and_port(url)  # 提取 IP 和端口
            for port in ports:
                future_to_url[executor.submit(get_domains_from_cert, ip, port)] = url

        # 收集解析结果
        to_add = set()
        for future in as_completed(future_to_url):
            original_url = future_to_url[future]
            try:
                domains = future.result()
                if domains:
                    for domain in domains:
                        new_url = replace_ip_with_domain(original_url, domain)
                        if validators.url(new_url):
                            to_add.add(new_url)
                    if to_add:
                        logging.info(
                            f"Found {len(to_add)} new URLs of {original_url}, {str(to_add)}."
                        )
            except Exception as e:
                logging.info(f"Error resolving host from {original_url}: {e}")
            finally:
                if progress_bar:
                    progress_bar.update(1)

        # 关闭进度条
        if progress_bar:
            progress_bar.close()

        # 更新 URL 列表
        url_list.update(to_add)

    return list(url_list)


def add_api_path(url: str, api_paths: Optional[list[str]]) -> list[str]:
    """
    为给定的 URL 拼接默认的 API 路径（仅当路径以 '/translate' 结尾时）。

    Args:
        url (str): 输入的 URL 字符串。
        api_paths (Optional[list[str]]): 默认 API 路径集合。

    Returns:
        list[str]: 拼接了默认 API 路径的 URL 列表。
                   如果输入 URL 不符合规则（如路径未以 '/translate' 结尾），返回空列表。
    """
    if not url or not api_paths:
        return []

    parsed_url = urlparse(url)
    path = parsed_url.path

    # 如果路径不以 "/translate" 结尾，直接返回空列表
    if not path.endswith("/translate"):
        return []
    for api_path in api_paths:
        if path.startswith("/" + api_path + "/"):
            path = path[len(api_path) + 2 :]

    # 使用集合去重并拼接新的路径
    url_list = {
        str(
            urlunparse(
                parsed_url._replace(
                    path="/".join([api_path.rstrip("/"), path.lstrip("/")])
                )
            )
        )
        for api_path in api_paths
    }

    # 返回去重后的 URL 列表
    return list(url_list)


def generate_urls(
    input_file: list[str] = FILE_PRIORITY,
    show_progress: bool = SHOW_SSL_PROGRESS_BAR,
    process_certificate: bool = PROCESS_CERTIFICATE,
    api_paths: list[str] = DEFAULT_API_BASE_PATH,
) -> list[str]:
    """
    入口函数：生成检测证书后的 URL 列表，并调用 add_api_path 拼接 API 路径。

    Args:
        input_file (list[str]): 输入文件路径，包含原始 URL 列表。
        show_progress (bool): 是否显示进度条，默认从配置中读取。
        process_certificate (bool): 是否检测证书，默认从配置中读取。
        api_paths (list[str]): API 路径列表。

    Returns:
        list[str]: 包含处理后的 URL 列表。
    """
    # 加载 URL 列表
    raw_urls = load_urls(input_file)
    if not raw_urls:
        logging.error("No valid URLs found in the input file.")
        return []

    if process_certificate:
        # 对 IP 类型的 URL 进行证书检测和域名替换
        processed_urls = make_url_list(raw_urls, show_progress)
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
    for url in processed_urls:
        for added_pathurl in add_api_path(url, api_paths):
            all_urls.add(added_pathurl)
        all_urls.add(url)

    # 去重返回最终的 URL 列表
    final_urls = list(set(all_urls))
    logging.info(f"Final URL count after adding API paths: {len(final_urls)}")
    return final_urls


if __name__ == "__main__":
    pass
