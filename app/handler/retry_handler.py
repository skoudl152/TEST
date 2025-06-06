# app/services/chat/retry_handler.py

from functools import wraps
from typing import Callable, TypeVar

from app.core.constants import MAX_RETRIES
from app.log.logger import get_retry_logger

T = TypeVar("T")
logger = get_retry_logger()


class RetryHandler:
    """重试处理装饰器"""

    def __init__(self, max_retries: int = MAX_RETRIES, key_arg: str = "api_key"):
        self.max_retries = max_retries
        self.key_arg = key_arg

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(self.max_retries):
                retries = attempt + 1
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"API call failed with error: {str(e)}. Attempt {retries} of {self.max_retries}"
                    )

                    # 从函数参数中获取 key_manager
                    key_manager = kwargs.get("key_manager")
                    if key_manager:
                        old_key = kwargs.get(self.key_arg)
                        new_key = await key_manager.handle_api_failure(old_key, retries)
                        if new_key:
                            kwargs[self.key_arg] = new_key
                            logger.info(f"Switched to new API key: {new_key}")
                        else:
                            logger.error(f"No valid API key available after {retries} retries.")
                            break

            logger.error(
                f"All retry attempts failed, raising final exception: {str(last_exception)}"
            )
            raise last_exception

        return wrapper
