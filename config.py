import os
import re

from dotenv import load_dotenv

load_dotenv()


def validate_rules(rules: dict) -> dict:
    """
    验证规则字典的正确性，确保 include_words 是列表，fail_regex 是字符串。

    参数:
        rules (dict): 待验证的规则字典。

    返回:
        dict: 验证通过的规则字典。如果验证失败，使用默认值代替。

    异常:
        ValueError: 如果规则的类型不符合要求，抛出错误。
    """
    # 验证 include_words
    include_words = rules.get("include_words", [])
    if not isinstance(include_words, list) or not all(
        isinstance(word, str) for word in include_words
    ):
        raise ValueError(
            f"'include_words' must be a list of strings. Got: {include_words}"
        )

    # 验证 fail_regex
    fail_regex = rules.get("fail_regex", "")
    if not isinstance(fail_regex, str):
        raise ValueError(f"'fail_regex' must be a string. Got: {fail_regex}")

    # 检查正则表达式是否可用
    try:
        re.compile(fail_regex)  # 测试编译
    except re.error as e:
        raise ValueError(
            f"Invalid regex pattern in 'fail_regex': {fail_regex}. Error: {e}"
        )

    # 返回验证后的规则
    return {"include_words": include_words, "fail_regex": fail_regex}


# ------------------------------
# Logging Configuration
# ------------------------------
# 日志级别，支持 DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "DEBUG"

# 日志格式，包含时间、日志名称、日志级别和消息
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 是否启用日志文件输出，如果为 True，日志将同时输出到文件
ENABLE_LOG_FILE_OUTPUT = True

# ------------------------------
# SSL Configuration
# ------------------------------
# 是否显示 SSL 检查的进度条，如果为 True，将显示进度条
SHOW_SSL_PROGRESS_BAR = False

# SSL 证书检查的最大并发工作线程数，用于控制并发检查的线程数量
SSL_CERT_CHECK_MAX_WORKERS = 128

# SSL 连接的最大允许延迟时间（秒），超过此时间将被视为超时
SSL_MAX_ALLOWED_LATENCY_SECONDS = 60

# ------------------------------
# URL Processing Configuration
# ------------------------------
# URL 处理的最大并发进程数，用于控制并发处理的进程数量
URL_PROCESSING_MAX_PROCESSES = 64

# URL 请求的最大允许延迟时间（秒），超过此时间将被视为超时
MAX_ALLOWED_LATENCY_SECONDS = 60

# ------------------------------
# Service Configuration
# ------------------------------
# 服务的默认端口号，用于指定 API 默认的的监听端口
SERVICE_DEFAULT_PORT = 1188

# ------------------------------
# Test Data
# ------------------------------
# 测试数据，包含一段文本及其源语言和目标语言
TEST_DATA = {"text": "Hello, world!", "source_lang": "EN", "target_lang": "ZH"}

# ------------------------------
# Reply Validation Rules
# ------------------------------
# 回复验证规则，包含需要包含的词语和失败的正则表达式
REPLY_RULE = validate_rules(
    {"include_words": ["你好", "世界"], "fail_regex": r"[\[\]{}()0-9]]"}
)

# ------------------------------
# API Configuration
# ------------------------------
# API 路径，从环境变量中获取，支持多个路径，以逗号分隔
ACCESS_TOKEN_PATH = os.getenv("ACCESS_TOKEN_PATH", "").split(",")

# 默认的 API 路径,默认包含 "v1"
DEFAULT_API_BASE_PATH = ["v1"]

# ------------------------------
# Data Processing Configuration
# ------------------------------
# 是否保存处理后的数据，如果为 True，处理后的数据将被保存
SAVE_PROCESSED_DATA = True

# 文件优先级列表，指定处理文件的优先级顺序
FILE_PRIORITY = ["urls.txt"]

# 是否将数据保存到文件，如果为 True，数据将被保存到文件中
SAVE_DATA_TO_FILE = True

# 是否处理证书，如果为 True，将执行证书处理逻辑
PROCESS_CERTIFICATE = True

# ------------------------------
# Request Headers
# ------------------------------
# HTTP 请求头，包含内容类型、设备信息、用户代理等
REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "x-app-os-name": "iOS",
    "x-app-os-version": "16.3.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "x-app-device": "iPhone13,2",
    "User-Agent": "DeepL-iOS/2.9.1 iOS 16.3.0 (iPhone13,2)",
    "x-app-build": "510265",
    "x-app-version": "2.9.1",
}

# ------------------------------
# External API Keys
# ------------------------------
# Shodan API 密钥，从环境变量中获取
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")

if __name__ == "__main__":
    pass
