"""Command decorators and utilities for command registration"""

import inspect
from typing import Optional, Any, Callable
from functools import wraps
from langchain_core.runnables import RunnableLambda

from .core.registry import registry


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


def command(name: str, app: Optional[str] = None):
    """
    Decorator to register a function as a command.
    
    Args:
        name: Command name
        app: App name (auto-detected if not provided)
        
    Returns:
        The decorated function with command registration
        
    Example:
        @command("process_text")
        def process_text(input_data: MyInput) -> MyOutput:
            return MyOutput(result="processed")
            
        @command("analyze", app="analytics") 
        def analyze_data(input_data: MyInput) -> MyOutput:
            return MyOutput(result="analyzed")
    """
    def decorator(func: Callable) -> Callable:
        app_name = app or _detect_app_name()
        runnable = RunnableLambda(func)
        try:
            registry.register(app_name, name, runnable)
        except Exception:
            # Registration failed, but return the function anyway
            # This allows the decorator to be robust against registry issues
            pass
        return func
    
    return decorator