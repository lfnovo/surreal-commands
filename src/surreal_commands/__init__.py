"""Surreal Commands - Distributed Task Queue Library"""

# Core functionality
from .core.registry import registry
from .core.service import CommandService, command_service
from .core.types import CommandRegistryItem, ExecutionContext, CommandInput, CommandOutput
from .core.retry import RetryConfig, RetryStrategy

# Decorator API
from .decorators import command

# Command execution and monitoring
from .core.client import (
    submit_command, 
    get_command_status, 
    get_command_status_sync,
    wait_for_command,
    wait_for_command_sync,
    execute_command_sync,
    CommandStatus,
    CommandResult
)

# Utilities for advanced usage
from .core.executor import CommandExecutor
from .repository import db_connection

__version__ = "1.0.0"

__all__ = [
    # Primary API - Command Registration
    "registry",
    "command",

    # Primary API - Command Execution & Monitoring
    "submit_command",
    "get_command_status",
    "get_command_status_sync",
    "wait_for_command",
    "wait_for_command_sync",
    "execute_command_sync",

    # Status and Result classes
    "CommandStatus",
    "CommandResult",

    # Service instances
    "CommandService",
    "command_service",

    # Base classes for commands
    "CommandInput",
    "CommandOutput",

    # Retry configuration
    "RetryConfig",
    "RetryStrategy",

    # Advanced usage
    "CommandRegistryItem",
    "ExecutionContext",
    "CommandExecutor",
    "db_connection",
]

# Rebuild CommandRegistryItem model now that RetryConfig is imported
# This resolves the forward reference "RetryConfig" to the actual class
CommandRegistryItem.model_rebuild()