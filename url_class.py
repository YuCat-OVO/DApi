import re
from dataclasses import dataclass, field
from typing import ClassVar
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

import validators

from config import DEFAULT_API_BASE_PATH, ACCESS_TOKEN_PATH, SERVICE_DEFAULT_PORT


@dataclass
class ApiURL:
    """API URL 数据类,用于处理、验证和生成 API URL。

    该类将输入的 URL 字符串解析为结构化的组件,并确保其有效性。
    支持 URL 规范化、主机验证、路径解析和查询参数处理。
    当两个 ApiURL 实例的主机相同时,可以通过加法运算符合并它们的端口、路径和查询参数。

    :param host: 主机名(域名或IP地址)
    :param has_domain: 是否包含域名,默认为 False
    :param scheme: URL 协议,默认为 "https"
    :param port_set: 端口号集合
    :param path_set: URL 路径段集合
    :param param_dict: URL 查询参数字典,每个参数可以有多个值
    :raises ValueError: 当 URL 格式无效或组件验证失败时
    """

    host: str
    has_domain: bool
    scheme: str = field(default="https")
    port_set: set[int] = field(default_factory=set)
    path_set: set[str] = field(default_factory=set)
    param_dict: dict[str, list[str]] = field(default_factory=dict)

    # 类常量
    _PORT_RANGE: ClassVar[tuple[int, int]] = (1, 65535)

    @classmethod
    def from_url(cls, url: str) -> "ApiURL":
        """从 URL 字符串创建 ApiURL 实例。

        :param url: 要解析的 URL 字符串
        :return: 包含解析后 URL 组件的 ApiURL 实例
        :raises ValueError: 当 URL 格式无效或组件验证失败时
        """
        normalized_url = cls._normalize_url(url)
        parsed_url = urlparse(normalized_url)

        if not cls._is_valid_url(normalized_url):
            raise ValueError(f"Invalid URL format: {url}")

        has_domain = False
        if cls._validate_domain(parsed_url.hostname):
            has_domain = True

        host = parsed_url.hostname
        port = {parsed_url.port} if parsed_url.port else set("")
        # 添加服务默认端口
        port.add(SERVICE_DEFAULT_PORT)
        path = cls._parse_path(parsed_url.path)
        query = cls._parse_query(parsed_url.query)

        return cls(
            host=host,
            has_domain=has_domain,
            port_set=port,
            path_set=path,
            param_dict=query,
        )

    @classmethod
    def replace_domain(cls, original: "ApiURL", domain: str) -> "ApiURL":
        """创建一个新的 ApiURL 实例，使用新的域名替换原有主机。
        注意：新的域名必须有效。

        :param original: 原始 ApiURL 实例
        :param domain: 新的域名
        :return: 新的 ApiURL 实例，具有新的域名和原始实例的其他属性
        :raises ValueError: 当新域名为空或格式无效时
        """
        if not domain or not domain.strip():
            raise ValueError("Empty host provided")

        if not cls._validate_domain(domain):
            raise ValueError(f"Invalid domain: {domain}")

        return cls(
            host=domain,
            has_domain=True,
            scheme=original.scheme,
            port_set=original.port_set.copy(),
            path_set=original.path_set.copy(),
            param_dict={k: v.copy() for k, v in original.param_dict.items()},
        )

    def generate_url_list(self) -> list[str]:
        """生成 URL 列表。

        :return: 包含所有有效 URL 的列表
        """
        ports = set(self.port_set or {""})
        ports.add(SERVICE_DEFAULT_PORT)

        return [
            urlunparse(
                (
                    scheme,
                    f"{self.host}:{port}" if port else self.host,
                    path,
                    "",  # fragment
                    urlencode(self.param_dict, doseq=True) if self.param_dict else "",
                    "",  # params
                )
            )
            for scheme in ("https", "http")
            for port in (ports | {443 if scheme == "https" else 80})
            for path in (self.path_set or [""])
        ]

    @staticmethod
    def _normalize_url(url: str) -> str:
        """标准化 URL。

        :param url: 要标准化的 URL 字符串
        :return: 标准化后的 URL 字符串
        :raises ValueError: 当提供空 URL 时
        """
        if not url:
            raise ValueError("Empty URL provided")

        url = url.strip()
        url = re.sub(r"/+$", "", url)

        if url.startswith("http://"):
            url = f"https://{url[7:]}"
        elif not url.startswith("https://"):
            url = f"https://{url}"

        return url

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """验证 URL 格式是否有效。

        :param url: 要验证的 URL 字符串
        :return: URL 格式是否有效
        """
        return bool(validators.url(url))

    @staticmethod
    def _validate_ip(ip: str) -> bool:
        """验证 IP 地址有效性。

        :param ip: 要验证的 IP 地址
        :return: 布尔值,表示 IP 地址是否有效
        :raises ValueError: 当 IP 地址无效时
        """
        if not validators.ipv4(ip) and not validators.ipv6(ip):
            return False
        return True

    @staticmethod
    def _validate_domain(domain: str) -> bool:
        """验证域名有效性。

        :param domain: 要验证的域名
        :return: 布尔值,表示域名是否有效
        :raises ValueError: 当域名无效时
        """
        if not validators.domain(domain):
            return False
        return True

    @staticmethod
    def _parse_query(query: str) -> dict[str, list[str]]:
        """解析查询字符串为字典。

        :param query: 要解析的查询字符串
        :return: 解析后的查询参数字典
        :raises ValueError: 当查询字符串格式无效时
        """
        try:
            return parse_qs(query)
        except ValueError as e:
            raise ValueError(f"Invalid param_dict string: {query}") from e

    @staticmethod
    def _parse_path(path: str) -> set[str]:
        """解析并验证 API 路径。

        处理三种情况:

        1. 空路径或默认基础路径
        2. 访问令牌路径
        3. 自定义 API 端点

        :param path: 要解析的路径字符串
        :return: 有效路径的集合
        """
        normalized_path = re.sub(r"/+$", "", path)
        if normalized_path.endswith("/translate"):
            normalized_path = normalized_path[:-10]
        valid_paths = set()

        # 处理空路径和默认路径
        if normalized_path == "" or any(
            normalized_path == f"/{base.rstrip('/')}" for base in DEFAULT_API_BASE_PATH
        ):
            valid_paths.add("/translate")
            for base in DEFAULT_API_BASE_PATH:
                valid_paths.add(f"/{base.rstrip('/')}/translate")

        # 处理令牌路径
        elif any(
            normalized_path == f"/{token.rstrip('/')}" for token in ACCESS_TOKEN_PATH
        ):
            valid_paths.add(f"{normalized_path}/translate")
        # 自定义API端点
        else:
            valid_paths.add(normalized_path)

        return valid_paths

    def __add__(self, other: "ApiURL") -> "ApiURL":
        """实现两个 ApiURL 实例的加法运算。

        :param other: 另一个 ApiURL 实例
        :return: 合并后的新 ApiURL 实例
        :raises ValueError: 当两个实例的域名不同时

        当两个实例的域名相同时,合并它们的端口、路径和查询参数。
        """
        if not isinstance(other, ApiURL):
            return NotImplemented

        if self.host != other.host:
            raise ValueError("Cannot add ApiURLs with different domains")

        # 合并端口
        new_port = self.port_set | other.port_set

        # 合并路径
        new_path = self.path_set | other.path_set

        # 合并查询参数
        new_query = self.param_dict.copy()
        for key, value in other.param_dict.items():
            if key in new_query:
                new_query[key] = list(set(new_query[key] + value))
            else:
                new_query[key] = value

        return ApiURL(
            host=self.host,
            has_domain=self.has_domain,
            port_set=new_port,
            path_set=new_path,
            param_dict=new_query,
        )

    def __hash__(self) -> int:
        """计算实例的哈希值。

        :return: 哈希值
        """
        return hash(self.host)


if __name__ == "__main__":
    pass
    url1 = ApiURL.from_url("https://api.example.com:7777/translate?lang=en")
    print(url1)
    print(url1.generate_url_list())
