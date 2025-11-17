"""
统一日志工具 - 提供结构化、可追踪的日志输出
"""
import logging
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime


class StructuredLogger:
    """
    结构化日志记录器，提供统一的日志格式和追踪ID支持
    """

    def __init__(self, name: str, request_id: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.request_id = request_id

    def _format_message(self, message: str, **kwargs) -> str:
        """
        格式化日志消息，包含统一的上下文信息
        """
        # 构建基础消息
        if self.request_id:
            formatted_message = f"[{self.request_id}] {message}"
        else:
            formatted_message = message

        # 添加额外上下文信息
        if kwargs:
            context_str = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            formatted_message += f" | {context_str}"

        return formatted_message

    def info(self, message: str, **kwargs):
        """记录INFO级别日志"""
        formatted_msg = self._format_message(message, **kwargs)
        self.logger.info(formatted_msg)

    def warning(self, message: str, **kwargs):
        """记录WARNING级别日志"""
        formatted_msg = self._format_message(message, **kwargs)
        self.logger.warning(formatted_msg)

    def error(self, message: str, **kwargs):
        """记录ERROR级别日志"""
        formatted_msg = self._format_message(message, **kwargs)
        self.logger.error(formatted_msg)

    def debug(self, message: str, **kwargs):
        """记录DEBUG级别日志"""
        formatted_msg = self._format_message(message, **kwargs)
        self.logger.debug(formatted_msg)

    def log_webhook_inbound(self, event_type: str, project_id: int, project_name: str, mr_iid: Optional[int] = None, **kwargs):
        """记录Webhook入站日志"""
        self.info(
            f"Webhook入站 - 事件类型:{event_type}, 项目:{project_name}(ID:{project_id})",
            event_type=event_type,
            project_id=project_id,
            project_name=project_name,
            mr_iid=mr_iid,
            stage="webhook_inbound",
            **kwargs
        )

    def log_thread_start(self, project_id: int, mr_iid: int, **kwargs):
        """记录处理线程启动日志"""
        self.info(
            f"启动MR审查线程 - 项目ID:{project_id}, MR IID:{mr_iid}",
            project_id=project_id,
            mr_iid=mr_iid,
            stage="thread_start",
            **kwargs
        )

    def log_gitlab_interaction(self, action: str, project_id: int, mr_iid: int, success: bool, duration: float = None, **kwargs):
        """记录GitLab交互日志"""
        status = "成功" if success else "失败"
        duration_str = f", 耗时:{duration:.2f}秒" if duration else ""

        message = f"GitLab交互{status} - 动作:{action}, 项目ID:{project_id}, MR IID:{mr_iid}{duration_str}"

        log_kwargs = {
            "action": action,
            "project_id": project_id,
            "mr_iid": mr_iid,
            "success": success,
            "stage": "gitlab_interaction",
            **kwargs
        }

        if duration:
            log_kwargs["duration"] = f"{duration:.2f}s"

        if success:
            self.info(message, **log_kwargs)
        else:
            self.error(message, **log_kwargs)

    def log_llm_call(self, provider: str, model: str, success: bool, duration: float = None, prompt_length: int = None, response_length: int = None, error: str = None, **kwargs):
        """记录LLM调用日志"""
        status = "成功" if success else "失败"
        duration_str = f", 耗时:{duration:.2f}秒" if duration else ""
        prompt_str = f", Prompt长度:{prompt_length}" if prompt_length else ""
        response_str = f", 响应长度:{response_length}" if response_length else ""

        message = f"LLM调用{status} - 提供商:{provider}, 模型:{model}{duration_str}{prompt_str}{response_str}"

        log_kwargs = {
            "llm_provider": provider,
            "llm_model": model,
            "success": success,
            "stage": "llm_call",
            **kwargs
        }

        if duration:
            log_kwargs["duration"] = f"{duration:.2f}s"
        if prompt_length:
            log_kwargs["prompt_length"] = prompt_length
        if response_length:
            log_kwargs["response_length"] = response_length
        if error:
            log_kwargs["error"] = error

        if success:
            self.info(message, **log_kwargs)
        else:
            self.error(message, **log_kwargs)

    def log_report_generation(self, is_mock: bool, score: float = None, file_count: int = None, success: bool = True, **kwargs):
        """记录报告生成日志"""
        mode = "Mock" if is_mock else "Real"
        status = "成功" if success else "失败"
        score_str = f", 评分:{score}" if score is not None else ""
        file_str = f", 文件数:{file_count}" if file_count else ""

        message = f"报告生成{status} - 模式:{mode}{score_str}{file_str}"

        log_kwargs = {
            "mode": mode,
            "success": success,
            "stage": "report_generation",
            **kwargs
        }

        if score is not None:
            log_kwargs["score"] = score
        if file_count:
            log_kwargs["file_count"] = file_count

        if success:
            self.info(message, **log_kwargs)
        else:
            self.error(message, **log_kwargs)

    def log_notification_dispatch(self, total_channels: int, success_channels: int, failed_channels: int, duration: float = None, **kwargs):
        """记录通知分发日志"""
        duration_str = f", 耗时:{duration:.2f}秒" if duration else ""

        message = f"通知分发完成 - 总渠道:{total_channels}, 成功:{success_channels}, 失败:{failed_channels}{duration_str}"

        log_kwargs = {
            "total_channels": total_channels,
            "success_channels": success_channels,
            "failed_channels": failed_channels,
            "stage": "notification_dispatch",
            **kwargs
        }

        if duration:
            log_kwargs["duration"] = f"{duration:.2f}s"

        self.info(message, **log_kwargs)

    def log_channel_notification(self, channel: str, success: bool, duration: float = None, error: str = None, **kwargs):
        """记录单个渠道通知日志"""
        status = "成功" if success else "失败"
        duration_str = f", 耗时:{duration:.2f}秒" if duration else ""

        message = f"通知{status} - 渠道:{channel}{duration_str}"

        log_kwargs = {
            "channel": channel,
            "success": success,
            "stage": "channel_notification",
            **kwargs
        }

        if duration:
            log_kwargs["duration"] = f"{duration:.2f}s"
        if error:
            log_kwargs["error"] = error

        if success:
            self.info(message, **log_kwargs)
        else:
            self.error(message, **log_kwargs)

    def log_database_operation(self, operation: str, table: str, success: bool, record_id: int = None, **kwargs):
        """记录数据库操作日志"""
        status = "成功" if success else "失败"
        record_str = f", 记录ID:{record_id}" if record_id else ""

        message = f"数据库操作{status} - 操作:{operation}, 表:{table}{record_str}"

        log_kwargs = {
            "operation": operation,
            "table": table,
            "success": success,
            "stage": "database_operation",
            **kwargs
        }

        if record_id:
            log_kwargs["record_id"] = record_id

        if success:
            self.info(message, **log_kwargs)
        else:
            self.error(message, **log_kwargs)

    def log_performance(self, operation: str, duration: float, **kwargs):
        """记录性能日志"""
        message = f"性能指标 - 操作:{operation}, 耗时:{duration:.2f}秒"

        self.info(
            message,
            operation=operation,
            duration=f"{duration:.2f}s",
            stage="performance",
            **kwargs
        )

    def log_business_metric(self, metric_name: str, value: Any, **kwargs):
        """记录业务指标日志"""
        self.info(
            f"业务指标 - {metric_name}:{value}",
            metric_name=metric_name,
            value=value,
            stage="business_metric",
            **kwargs
        )

    def log_error_with_context(self, error: Exception, context: Dict[str, Any] = None, **kwargs):
        """记录带上下文的错误日志"""
        context = context or {}
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stage": "error",
            **context,
            **kwargs
        }

        self.error(
            f"发生异常: {type(error).__name__} - {str(error)}",
            **error_info
        )


def get_logger(name: str, request_id: Optional[str] = None) -> StructuredLogger:
    """
    获取结构化日志记录器实例

    Args:
        name: 日志记录器名称
        request_id: 请求追踪ID

    Returns:
        StructuredLogger实例
    """
    return StructuredLogger(name, request_id)


# 性能计时器装饰器
def log_execution_time(logger: StructuredLogger, operation_name: str):
    """
    装饰器：记录函数执行时间

    Args:
        logger: 结构化日志记录器
        operation_name: 操作名称
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.log_performance(operation_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.log_error_with_context(
                    e,
                    context={"operation": operation_name, "duration": f"{duration:.2f}s"}
                )
                raise
        return wrapper
    return decorator


# 上下文管理器用于计时
class TimerContext:
    """
    计时上下文管理器
    """

    def __init__(self, logger: StructuredLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if exc_type is None:
            self.logger.log_performance(self.operation, duration)
        else:
            self.logger.log_error_with_context(
                exc_val,
                context={"operation": self.operation, "duration": f"{duration:.2f}s"}
            )