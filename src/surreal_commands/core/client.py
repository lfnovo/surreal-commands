"""Client API for command submission and monitoring"""

import asyncio
import time
from enum import Enum
from typing import Any, Dict, Optional, Union

from surrealdb import RecordID

from ..repository import ensure_record_id
from .service import CommandRequest, command_service


class CommandStatus(str, Enum):
    """Command execution status"""

    NEW = "new"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class CommandResult:
    """Command result with status and data"""

    def __init__(
        self,
        command_id: Union[str, RecordID],
        status: CommandStatus,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        created: Optional[str] = None,
        updated: Optional[str] = None,
    ):
        self.command_id = ensure_record_id(command_id)
        self.status = status
        self.result = result
        self.error_message = error_message
        self.created = created
        self.updated = updated

    def is_complete(self) -> bool:
        """Check if command execution is complete (successful or failed)"""
        return self.status in (
            CommandStatus.COMPLETED,
            CommandStatus.FAILED,
            CommandStatus.CANCELED,
        )

    def is_success(self) -> bool:
        """Check if command completed successfully"""
        return self.status == CommandStatus.COMPLETED


def submit_command(
    app: str,
    command: str,
    args: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Submit a command for execution and return the command ID.

    Args:
        app: Application name
        command: Command name
        args: Command arguments
        context: Optional context data

    Returns:
        str: Command ID for tracking

    Example:
        >>> cmd_id = submit_command("my_app", "process_data", {"text": "hello"})
        >>> print(f"Submitted command: {cmd_id}")
    """
    request = CommandRequest(app=app, command=command, args=args, context=context)
    return command_service.submit_command_sync(request)


async def get_command_status(command_id: Union[str, RecordID]) -> CommandResult:
    """
    Get current status and result of a command.

    Args:
        command_id: The command ID returned from submit_command

    Returns:
        CommandResult: Object with status, result data, and metadata

    Example:
        >>> result = await get_command_status("command:abc123")
        >>> if result.is_complete():
        >>>     print(f"Result: {result.result}")
    """
    from ..repository import repo_query

    commands = await repo_query(
        "SELECT * FROM $command_id", {"command_id": ensure_record_id(command_id)}
    )
    if not commands:
        raise ValueError(f"Command {command_id} not found")

    cmd = commands[0]
    return CommandResult(
        command_id=cmd["id"],
        status=CommandStatus(cmd["status"]),
        result=cmd.get("result"),
        error_message=cmd.get("error_message"),
        created=cmd.get("created"),
        updated=cmd.get("updated"),
    )


def get_command_status_sync(command_id: Union[str, RecordID]) -> CommandResult:
    """Synchronous version of get_command_status"""
    return asyncio.run(get_command_status(command_id))


async def wait_for_command(
    command_id: Union[str, RecordID],
    timeout: Optional[float] = None,
    poll_interval: float = 1.0,
) -> CommandResult:
    """
    Wait for a command to complete and return the final result.

    Args:
        command_id: The command ID to wait for
        timeout: Maximum time to wait in seconds (None = wait forever)
        poll_interval: How often to check status in seconds

    Returns:
        CommandResult: Final command result

    Raises:
        TimeoutError: If timeout is reached before completion

    Example:
        >>> cmd_id = submit_command("my_app", "long_task", {"data": [1,2,3]})
        >>> result = await wait_for_command(cmd_id, timeout=60)
        >>> print(f"Task completed: {result.result}")
    """
    start_time = time.time()

    while True:
        result = await get_command_status(command_id)

        if result.is_complete():
            return result

        if timeout and (time.time() - start_time) > timeout:
            raise TimeoutError(
                f"Command {command_id} did not complete within {timeout} seconds"
            )

        await asyncio.sleep(poll_interval)


def wait_for_command_sync(
    command_id: Union[str, RecordID],
    timeout: Optional[float] = None,
    poll_interval: float = 1.0,
) -> CommandResult:
    """Synchronous version of wait_for_command"""
    return asyncio.run(wait_for_command(command_id, timeout, poll_interval))


def execute_command_sync(
    app: str,
    command: str,
    args: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> CommandResult:
    """
    Submit a command and wait for its completion.

    Args:
        app: Application name
        command: Command name
        args: Command arguments
        context: Optional context
        timeout: Maximum wait time

    Returns:
        CommandResult: Final result

    Example:
        >>> result = execute_command_sync("my_app", "quick_task", {"x": 5})
        >>> if result.is_success():
        >>>     print(result.result)
    """
    cmd_id = submit_command(app, command, args, context)
    return wait_for_command_sync(cmd_id, timeout)
