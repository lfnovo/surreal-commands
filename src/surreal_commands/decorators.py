"""Command decorators and utilities for command registration"""

import inspect
from typing import Optional, Any, Callable, Dict, Union
from langchain_core.runnables import RunnableLambda
from loguru import logger

from .core.registry import registry
from .core.retry import RetryConfig


def _detect_app_name() -> str:
    """Auto-detect app name from calling module"""
    frame = inspect.currentframe()
    try:
        # Go up the call stack to find the caller
        caller_frame = frame.f_back.f_back
        module = inspect.getmodule(caller_frame)
        
        if module and module.__name__ != "__main__":
            # Extract package name (first part before .)
            parts = module.__name__.split('.')
            return parts[0]
        
        # Fallback to "app" if can't detect
        return "app"
    finally:
        del frame


def command(
    name: str,
    app: Optional[str] = None,
    retry: Optional[Union[Dict[str, Any], RetryConfig]] = None
):
    """
    Decorator to register a function as a command.

    Args:
        name: Command name
        app: App name (auto-detected if not provided)
        retry: Retry configuration (dict or RetryConfig instance)
               Set to None or {"enabled": False} to disable retries

    Returns:
        The decorated function with command registration

    Example:
        @command("process_text")
        def process_text(input_data: MyInput) -> MyOutput:
            return MyOutput(result="processed")

        @command("analyze", app="analytics", retry={"max_attempts": 3, "wait": "exponential"})
        def analyze_data(input_data: MyInput) -> MyOutput:
            return MyOutput(result="analyzed")

        @command("no_retry", retry=None)  # Explicitly disable retries
        def no_retry_command(input_data: MyInput) -> MyOutput:
            return MyOutput(result="no retry")
    """
    def decorator(func: Callable) -> Callable:
        app_name = app or _detect_app_name()
        runnable = RunnableLambda(func)

        # Parse retry configuration
        retry_config = None
        if retry is not None:
            if isinstance(retry, dict):
                # Check if explicitly disabled
                if retry.get("enabled") is False:
                    retry_config = None
                    logger.debug(f"Retry explicitly disabled for command {app_name}.{name}")
                else:
                    try:
                        retry_config = RetryConfig(**retry)
                        logger.debug(f"Retry config parsed for command {app_name}.{name}: {retry_config}")
                    except Exception as e:
                        logger.error(f"Failed to parse retry config for {app_name}.{name}: {e}")
                        retry_config = None
            elif isinstance(retry, RetryConfig):
                retry_config = retry if retry.enabled else None

        try:
            registry.register(app_name, name, runnable, retry_config=retry_config)
        except Exception as e:
            # Registration failed, but return the function anyway
            # This allows the decorator to be robust against registry issues
            logger.error(f"Failed to register command {app_name}.{name}: {e}")
            pass
        return func

    return decorator