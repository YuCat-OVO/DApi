import logging
import socket
import ssl
from typing import Optional, cast

import validators
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import DNSName, SubjectAlternativeName, Certificate
from cryptography.x509.oid import NameOID, ExtensionOID

from config import SSL_MAX_ALLOWED_LATENCY_SECONDS


def validate_and_normalize_domain(domain: str) -> Optional[str]:
    """
    验证域名是否合法，并对通配符域名进行规范化。

    Args:
        domain (str): 待验证的域名。

    Returns:
        Optional[str]: 合法域名或 None。
    """
    domain = domain.strip().lower()
    if domain.startswith("*."):
        domain = domain[2:]  # 移除通配符前缀
    return domain if validators.domain(domain) else None


def try_connection(
    ip: str, port: int, ssl_sock_timeout: int = SSL_MAX_ALLOWED_LATENCY_SECONDS
) -> Optional[bytes]:
    """
    使用默认的 SSL 上下文连接服务器并获取证书。

    Args:
        ip (str): 目标 IP 地址或域名。
        port (int): 目标端口。
        ssl_sock_timeout (int): SSL 连接超时时间。

    Returns:
        Optional[bytes]: 服务器的证书字节数据，如果连接失败返回 None。
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with context.wrap_socket(
            socket.socket(socket.AF_INET), server_hostname=ip
        ) as sock:
            sock.settimeout(ssl_sock_timeout)
            sock.connect((ip, port))
            return sock.getpeercert(binary_form=True)
    except (ssl.SSLError, ConnectionError, TimeoutError) as e:
        if isinstance(e, ssl.SSLError):
            logging.debug(
                f"Port {port} on {ip} may not be SSL-enabled or the server has SSL misconfiguration."
            )
        else:
            logging.debug(f"Failed to connect to {ip}:{port}. Error: {str(e)}")
    return None


def extract_domains_from_cert(cert: Certificate) -> list[str]:
    """
    从证书中提取域名，包括 CN 和 SAN。

    Args:
        cert (Certificate): 解析后的证书对象。

    Returns:
        list[str]: 提取到的合法域名。
    """
    domains = set()

    # 提取 CN (Common Name)
    try:
        cn_attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        for attr in cn_attributes:
            normalized_domain = validate_and_normalize_domain(attr.value.strip())
            if normalized_domain:
                domains.add(normalized_domain)
    except Exception as e:
        logging.debug(f"Failed to extract CN: {str(e)}")

    # 提取 SAN (Subject Alternative Name)
    try:
        san_extension = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        if isinstance(san_extension.value, SubjectAlternativeName):
            san = cast(SubjectAlternativeName, san_extension.value)
            for entry in san:
                if isinstance(entry, DNSName):
                    normalized_domain = validate_and_normalize_domain(
                        entry.value.strip()
                    )
                    if normalized_domain:
                        domains.add(normalized_domain)
    except Exception as e:
        logging.debug(f"Failed to extract SAN: {str(e)}")

    return list(domains)


def get_domains_from_cert(ip: str, port: int) -> list[str]:
    """
    尝试连接目标服务器并提取 SSL 证书中的域名。

    Args:
        ip (str): 目标 IP 地址或域名。
        port (int): 目标端口。

    Returns:
        list[str]: 从证书中提取的合法域名列表。
    """
    try:
        cert_bin = try_connection(ip, port)
        if not cert_bin:
            logging.debug(f"Unable to retrieve certificate from {ip}:{port}")
            return []

        cert = x509.load_der_x509_certificate(cert_bin, default_backend())
        domains = extract_domains_from_cert(cert)
        return domains
    except Exception as e:
        logging.debug(f"Failed to parse certificate for {ip}:{port}: {str(e)}")
        return []


if __name__ == "__main__":
    pass
