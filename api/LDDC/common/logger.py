# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only

"""Web环境专用日志记录器"""

import json
import logging
import os
import sys
import time
from logging import CRITICAL, DEBUG, ERROR, INFO, NOTSET, WARNING, LogRecord
from typing import Any, Dict

# Web环境配置
class WebConfig:
    """Web环境配置模拟"""
    def __init__(self):
        self._config = {
            "log_level": os.environ.get("LDDC_LOG_LEVEL", "INFO")
        }
    
    def __getitem__(self, key: str) -> Any:
        return self._config.get(key)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

# 模拟args模块
class WebArgs:
    def __init__(self):
        self.get_service_port = False

# 模拟paths模块
def get_log_dir():
    """获取日志目录（Web环境使用临时目录）"""
    import tempfile
    temp_base = tempfile.gettempdir()
    log_dir = os.path.join(temp_base, "LDDC", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# Web环境使用模拟的cfg和args
cfg = WebConfig()
args = WebArgs()
log_dir = get_log_dir()

log_file = os.path.join(log_dir, f'{time.strftime("%Y.%m.%d", time.localtime())}.log')


def str2log_level(level: str) -> int:
    """将字符串日志级别转换为logging常量"""
    level_upper = level.upper()
    level_map = {
        "NOTSET": NOTSET,
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
    }
    return level_map.get(level_upper, INFO)


class JSONFormatter(logging.Formatter):
    """JSON格式的日志格式化器，适合Web环境"""
    def format(self, record: LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "logger": record.name,
        }
        
        # 添加额外字段
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """控制台友好的日志格式化器"""
    def __init__(self):
        super().__init__(
            '[%(levelname)s] %(asctime)s - %(module)s:%(lineno)d - %(funcName)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


class Logger:
    def __init__(self) -> None:
        self.name = 'LDDC'
        self.__logger = logging.getLogger(self.name)
        
        # 避免重复添加handler
        if self.__logger.handlers:
            self.__logger.handlers.clear()
        
        self.level = str2log_level(cfg["log_level"])
        self.__logger.setLevel(self.level)
        self.__logger.propagate = False
        
        # 文件处理器（JSON格式）
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(JSONFormatter())
            file_handler.setLevel(self.level)
            self.__logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            # 如果无法写入文件，只使用控制台输出
            print(f"Warning: Cannot write log file: {e}")
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ConsoleFormatter())
        console_handler.setLevel(self.level)
        self.__logger.addHandler(console_handler)
        
        # 绑定日志方法
        self.debug = self.__logger.debug
        self.info = self.__logger.info
        self.warning = self.__logger.warning
        self.error = self.__logger.error
        self.critical = self.__logger.critical
        self.log = self.__logger.log
        self.exception = self.__logger.exception
    
    def set_level(self, level: int | str) -> None:
        """设置日志级别"""
        if isinstance(level, str):
            level = str2log_level(level)
        
        self.level = level
        self.__logger.setLevel(level)
        
        for handler in self.__logger.handlers:
            handler.setLevel(level)
    
    def get_log_file_path(self) -> str:
        """获取日志文件路径"""
        return log_file
    
    def log_request(self, request_data: Dict[str, Any]) -> None:
        """记录HTTP请求（Web专用）"""
        extra_data = {
            "type": "http_request",
            "method": request_data.get("method"),
            "path": request_data.get("path"),
            "ip": request_data.get("ip"),
            "user_agent": request_data.get("user_agent"),
            "duration_ms": request_data.get("duration_ms"),
        }
        self.info(f"HTTP {request_data.get('method')} {request_data.get('path')}", 
                  extra={"extra": extra_data})
    
    def log_api_response(self, api_data: Dict[str, Any]) -> None:
        """记录API响应（Web专用）"""
        extra_data = {
            "type": "api_response",
            "endpoint": api_data.get("endpoint"),
            "status": api_data.get("status"),
            "response_time_ms": api_data.get("response_time_ms"),
            "result_count": api_data.get("result_count"),
        }
        self.info(f"API Response: {api_data.get('endpoint')} - {api_data.get('status')}", 
                  extra={"extra": extra_data})


# 创建全局logger实例
logger = Logger()

# 设置第三方库的日志级别
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)


def setup_flask_logging(app):
    """为Flask应用设置日志（可选）"""
    if not app.debug:
        # 在生产环境中，添加访问日志
        import logging
        from logging.handlers import RotatingFileHandler
        
        # 访问日志
        access_log = logging.getLogger('werkzeug')
        access_log.setLevel(logging.INFO)
        
        # 访问日志文件处理器
        access_log_file = os.path.join(log_dir, 'access.log')
        file_handler = RotatingFileHandler(
            access_log_file, maxBytes=1024 * 1024 * 10, backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        access_log.addHandler(file_handler)
        
        # 移除默认的控制台处理器
        access_log.handlers = [h for h in access_log.handlers 
                              if not isinstance(h, logging.StreamHandler)]
        
        logger.info("Flask logging setup complete")
