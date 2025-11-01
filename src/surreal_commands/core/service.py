"""
Command Service for handling command lifecycle from submission to execution.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from surrealdb import AsyncSurreal, Surreal

from .executor import CommandExecutor
from .registry import registry
from .types import ExecutionContext
from .retry import (
    get_global_retry_config,
    merge_retry_configs,
    build_async_retry_instance,
)
from tenacity import RetryError

load_dotenv()


class CommandRequest(BaseModel):
    """Model representing a command request to be submitted to the queue."""

    app: str
    command: str
    args: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


class CommandResponse(BaseModel):
    """Model representing a command response after execution."""

    command_id: str
    result: Any
    status: str = "completed"
    error: Optional[str] = None


class CommandService:
    """
    Service for managing the lifecycle of commands.
    Handles submission, execution, and result management.
    """

    def __init__(self, db_url: Optional[str] = None):
        surreal_url = (
            db_url
            or os.environ.get("SURREAL_URL")
            or f"ws://{os.environ.get('SURREAL_ADDRESS', 'localhost')}:{os.environ.get('SURREAL_PORT', 8000)}/rpc"
        )
        self.db_url = surreal_url
        self.db_auth = {
            "username": os.environ.get("SURREAL_USER", "test"),
            "password": os.environ.get("SURREAL_PASSWORD")
            or os.environ.get("SURREAL_PASS", "test"),
        }
        self.db_namespace = os.environ.get("SURREAL_NAMESPACE", "test")
        self.db_database = os.environ.get("SURREAL_DATABASE", "test")
        self._executor = None

    @property
    def executor(self) -> CommandExecutor:
        """
        Lazy initialization of the executor to ensure all commands are registered.
        """
        if self._executor is None:
            logger.debug("Initializing command executor")
            commands = registry.get_all_commands()
            logger.debug(f"Found {len(commands)} commands")

            command_dict = {
                f"{item.app_id}.{item.name}": item.runnable for item in commands
            }

            # Log the commands for debugging
            for cmd_id in command_dict.keys():
                logger.debug(f"Registering command with executor: {cmd_id}")

            self._executor = CommandExecutor(command_dict)
        return self._executor

    async def submit_command(self, request: CommandRequest) -> str:
        """
        Submit a command to the queue for asynchronous execution.

        Args:
            request: The command request containing app, command, and arguments

        Returns:
            The ID of the created command in the queue
        """
        # Validate the command exists
        command_id = f"{request.app}.{request.command}"
        registry_item = registry.get_command_by_id(command_id)

        if not registry_item:
            raise ValueError(f"Command not found: {command_id}")

        # Validate arguments against the input schema
        input_schema = registry_item.input_schema
        validated_args = input_schema(**request.args).model_dump()

        # Submit to queue
        async with AsyncSurreal(self.db_url) as db:
            await db.signin(self.db_auth)
            await db.use(self.db_namespace, self.db_database)

            result = await db.create(
                "command",
                {
                    "app": request.app,
                    "name": request.command,
                    "args": validated_args,
                    "context": request.context or {},
                    "status": "new",
                },
            )

            command_id = result["id"]
            logger.debug(f"Submitted command to queue: {command_id}")
            return command_id

    def submit_command_sync(self, request: CommandRequest) -> str:
        """
        Synchronous version of submit_command.

        Args:
            request: The command request

        Returns:
            The ID of the created command in the queue
        """
        with Surreal(self.db_url) as db:
            db.signin(self.db_auth)
            db.use(self.db_namespace, self.db_database)

            # Validate the command exists
            command_id = f"{request.app}.{request.command}"
            registry_item = registry.get_command_by_id(command_id)

            if not registry_item:
                raise ValueError(f"Command not found: {command_id}")

            # Validate arguments against the input schema
            input_schema = registry_item.input_schema
            validated_args = input_schema(**request.args).model_dump(mode="json")

            result = db.create(
                "command",
                {
                    "app": request.app,
                    "name": request.command,
                    "args": validated_args,
                    "context": request.context or {},
                    "status": "new",
                },
            )

            command_id = result["id"]
            logger.debug(f"Submitted command to queue: {command_id}")
            return command_id

    async def execute_command(
        self,
        command_id: str,
        command_name: str,
        input_data: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a command by its name and input data.

        Args:
            command_id: The ID of the command in the queue
            command_name: The full name of the command (app.command)
            input_data: The input data for the command
            user_context: Optional user context from CLI

        Returns:
            The result of executing the command
        """
        logger.debug(f"Executing command: {command_name}")

        # Get command from registry
        registry_item = registry.get_command_by_id(command_name)
        if registry_item:
            # Use registry item's runnable
            command = registry_item.runnable
            logger.debug(f"Using registry item runnable for {command_name}")
        else:
            # Fallback for backward compatibility
            command = registry._commands.get(command_name)
            if not command:
                raise ValueError(f"Command not found: {command_name}")
            logger.debug(f"Using legacy command runnable for {command_name}")

        # Parse input and execute
        input_data = CommandExecutor.parse_input(command, input_data)

        # Create execution context
        app_name, cmd_name = command_name.split(".", 1)
        execution_context = ExecutionContext(
            command_id=command_id,
            execution_started_at=datetime.now(),
            app_name=app_name,
            command_name=cmd_name,
            user_context=user_context,
        )

        # Ensure executor is initialized with all commands
        executor = self.executor
        logger.debug(f"Executing command {command_name} with executor")

        # Get retry configuration (per-command or global)
        per_command_retry = registry_item.retry_config if registry_item else None
        global_retry = get_global_retry_config()
        retry_config = merge_retry_configs(global_retry, per_command_retry)

        await self.update_command_result(command_id, "running")

        result = None
        status = "completed"
        formatted_result = None
        error_message = ""

        # Define the execution function that will be retried
        async def execute_with_retry():
            return await executor.execute_async(
                command_name, input_data, execution_context
            )

        try:
            # If retry is enabled, wrap execution in retry logic
            if retry_config and retry_config.enabled:
                logger.debug(
                    f"Retry enabled for {command_name}: max_attempts={retry_config.max_attempts}, "
                    f"strategy={retry_config.wait_strategy}"
                )
                retry_instance = build_async_retry_instance(retry_config)

                # Execute with retry using context manager
                async for attempt in retry_instance:
                    with attempt:
                        result = await execute_with_retry()
            else:
                # No retry - execute directly
                logger.debug(f"Retry not enabled for {command_name}")
                result = await execute_with_retry()

            status = "completed"
            # Format result for storage
            formatted_result = None
            if isinstance(result, BaseModel):
                formatted_result = result.model_dump()
            elif not isinstance(result, dict) and not isinstance(result, list):
                formatted_result = {"output": str(result)}
            else:
                formatted_result = result

        except RetryError as e:
            # All retry attempts exhausted - get the original exception
            original_exception = e.last_attempt.exception()
            logger.error(
                f"Command {command_name} failed after all retry attempts: {original_exception}"
            )
            status = "failed"
            error_message = str(original_exception)

        except Exception as e:
            # Direct execution failed or retry not enabled
            logger.error(f"Error executing command {command_name}: {e}")
            status = "failed"
            error_message = str(e)

        # Update command status in queue
        # Status remains "running" during retries and only changes to completed/failed at the end
        await self.update_command_result(
            command_id, status, formatted_result, error_message
        )
        return result

    async def update_command_result(
        self,
        command_id: str,
        status: Literal["new", "running", "completed", "failed", "canceled"],
        result: Union[List, Dict] = {},
        error_message: Optional[str] = "",
    ) -> None:
        """Update the result of a command in the queue."""
        async with AsyncSurreal(self.db_url) as db:
            await db.signin(self.db_auth)
            await db.use(self.db_namespace, self.db_database)
            await db.merge(
                command_id,
                {"status": status, "result": result, "error_message": error_message},
            )


# Create a lazy-initialized singleton instance for global use
_command_service = None


def get_command_service() -> CommandService:
    """Get the global command service instance (lazy initialization)."""
    global _command_service
    if _command_service is None:
        _command_service = CommandService()
    return _command_service


# For backward compatibility, create a property-like access
class CommandServiceProxy:
    def __getattr__(self, name):
        return getattr(get_command_service(), name)

    def __call__(self, *args, **kwargs):
        return get_command_service()(*args, **kwargs)


command_service = CommandServiceProxy()
