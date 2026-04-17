"""Retry utilities with exponential backoff."""
import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    logger_instance: Optional[logging.Logger] = None,
):
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential calculation
        exceptions: Tuple of exceptions to catch and retry
        logger_instance: Logger to use (defaults to module logger)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_with_backoff(max_retries=3)
        def api_call():
            return requests.get("https://api.example.com")
    """
    log = logger_instance or logger
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        log.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts",
                            exc_info=True,
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay,
                    )
                    
                    log.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}). "
                        f"Retrying in {delay:.2f} seconds...",
                        exc_info=True,
                    )
                    
                    # Sleep before retry
                    import time
                    time.sleep(delay)
            
            # This should not be reached due to raise in the loop
            raise last_exception or Exception("Retry logic failed unexpectedly")
        
        return wrapper
    
    return decorator


def async_retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Async decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential calculation
        exceptions: Tuple of exceptions to catch and retry
    
    Returns:
        Decorated async function with retry logic
    
    Example:
        @async_retry_with_backoff(max_retries=3)
        async def api_call():
            async with httpx.AsyncClient() as client:
                return await client.get("https://api.example.com")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts",
                            exc_info=True,
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay,
                    )
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}). "
                        f"Retrying in {delay:.2f} seconds...",
                        exc_info=True,
                    )
                    
                    # Sleep before retry
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    
    return decorator
