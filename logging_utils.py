import logging

from config import LOG_LEVEL, LOG_FORMAT, ENABLE_LOG_FILE_OUTPUT


def setup_logger():
    """
    配置日志记录器，支持文件日志和控制台日志。

    日志级别、格式和是否启用文件日志根据配置动态调整。
    """
    # 确保日志配置不会重复添加处理器
    if logging.getLogger().hasHandlers():
        logging.getLogger().handlers.clear()

    # 将字符串日志等级转换为对应整数值
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)  # 默认INFO

    # 设置日志处理器列表
    handlers = [logging.StreamHandler()]  # 控制台输出处理器

    if ENABLE_LOG_FILE_OUTPUT:
        # 添加文件日志处理器
        handlers.append(logging.FileHandler("debug.log", encoding="utf-8"))

    # 配置日志基础设置
    logging.basicConfig(
        level=log_level,  # 动态设置日志等级
        format=LOG_FORMAT or "%(asctime)s - %(levelname)s - %(message)s",  # 默认格式
        handlers=handlers,
    )

    logging.info("Logger successfully configured!")
