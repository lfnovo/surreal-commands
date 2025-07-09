import asyncio
import inspect
import threading
from typing import Any, AsyncIterator, Iterator, Optional

from langchain_core.runnables import Runnable
from langchain_core.runnables.utils import AddableDict
from langgraph.graph.state import CompiledStateGraph
from loguru import logger
from pydantic import BaseModel

from .types import ExecutionContext, CommandInput, CommandOutput


class CommandExecutor:
    def __init__(self, command_dict: dict):
        """Initialize the CommandExecutor with a dictionary of commands."""
        self.command_dict = command_dict
        # Use a regular dict but with limited size to prevent memory leaks
        self._context_aware_cache = {}
        self._cache_max_size = 100  # Limit cache size

    def _command_accepts_execution_context(self, command: Runnable) -> bool:
        """Check if a command accepts execution_context parameter."""
        # Use caching for performance with size limits
        command_id = id(command)
        if command_id in self._context_aware_cache:
            return self._context_aware_cache[command_id]

        result = self._inspect_command_signature(command)
        
        # Limit cache size to prevent memory leaks
        if len(self._context_aware_cache) >= self._cache_max_size:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self._context_aware_cache))
            del self._context_aware_cache[oldest_key]
        
        self._context_aware_cache[command_id] = result
        return result

    def _inspect_command_signature(self, command: Runnable) -> bool:
        """Inspect command signature to determine if it accepts execution_context."""
        try:
            # For RunnableLambda, check both sync (func) and async (afunc) functions
            func = None
            if hasattr(command, "func"):
                func = command.func
            elif hasattr(command, "afunc"):
                func = command.afunc

            if func:
                signature = inspect.signature(func)
                # Check if there's an execution_context parameter
                return "execution_context" in signature.parameters

            # For other runnables, we assume they don't accept execution_context
            return False
        except (ValueError, TypeError) as e:
            # Log specific errors for debugging
            logger.debug(f"Failed to inspect command signature: {e}")
            return False
        except Exception as e:
            # Catch any other unexpected errors
            logger.warning(f"Unexpected error during signature inspection: {e}")
            return False

    def _prepare_command_args(
        self,
        command: Runnable,
        args: Any,
        execution_context: Optional[ExecutionContext] = None,
    ) -> Any:
        """Prepare arguments for command execution, potentially including execution_context."""
        if not execution_context:
            return args

        # If args is an instance of CommandInput, set the execution_context directly
        if isinstance(args, CommandInput):
            args.execution_context = execution_context
            return args
        
        # For backward compatibility: if function explicitly accepts execution_context parameter
        if self._command_accepts_execution_context(command):
            if isinstance(args, dict):
                return {**args, "execution_context": execution_context}
            elif isinstance(args, BaseModel):
                # For Pydantic models, check if they support execution_context
                try:
                    # Try to add execution_context to the model's dict representation
                    args_dict = args.model_dump()
                    args_dict["execution_context"] = execution_context
                    return args_dict
                except (TypeError, ValueError):
                    # Model doesn't support execution_context field
                    logger.debug(
                        f"Cannot inject execution_context into Pydantic model {type(args)}"
                    )
                    return args
            else:
                # For other argument types, we can't inject execution_context
                logger.debug(
                    f"Cannot inject execution_context into argument type {type(args)}"
                )
                return args
        
        return args

    @classmethod
    def parse_input(self, runnable, args) -> Any:
        target_schema = runnable.get_input_schema()
        if issubclass(target_schema, BaseModel):
            if isinstance(args, target_schema):
                return args
            elif isinstance(args, dict):
                return target_schema(**args)
        elif issubclass(target_schema, AddableDict) or issubclass(target_schema, dict):
            if isinstance(args, target_schema):
                return args
            elif isinstance(args, dict):
                return target_schema(args)
            elif isinstance(args, BaseModel):
                return target_schema(**args.model_dump())

        return args

    def _populate_command_output(
        self, 
        output: Any, 
        execution_context: Optional[ExecutionContext] = None,
        execution_time: Optional[float] = None
    ) -> Any:
        """Populate CommandOutput fields if the output inherits from CommandOutput."""
        if isinstance(output, CommandOutput) and execution_context:
            # Only set fields that are None (don't override user-set values)
            if output.command_id is None:
                output.command_id = str(execution_context.command_id)
            if output.execution_time is None and execution_time is not None:
                output.execution_time = execution_time
            if output.execution_metadata is None:
                output.execution_metadata = {
                    "app_name": execution_context.app_name,
                    "command_name": execution_context.command_name,
                    "started_at": execution_context.execution_started_at.isoformat()
                }
        return output

    def _fix_return_type(self, return_class: Any, value: Any) -> Any:
        """
        Ensure the return value matches the expected type.

        Args:
            return_class: The expected return type.
            value: The value to fix.

        Returns:
            The value, converted to the expected type if necessary.
        """
        # Handle LangChain auto-generated schema objects
        if hasattr(value, "__dict__") and hasattr(value, "__class__"):
            class_name = value.__class__.__name__
            if "_output" in class_name.lower() or "output" in class_name.lower():
                # LangChain auto-generated schema object, convert to dict
                if hasattr(value, "model_dump"):
                    # Pydantic model
                    value = value.model_dump()
                elif hasattr(value, "__dict__"):
                    # Generic object, use __dict__
                    value = value.__dict__

        # Only apply type checking if return_class is a class and not Any
        if isinstance(return_class, type):
            if issubclass(return_class, BaseModel):
                if isinstance(value, return_class):
                    return value
                elif isinstance(value, dict):
                    return return_class(**value)
            elif issubclass(return_class, AddableDict):
                if isinstance(value, return_class):
                    return value
                elif isinstance(value, dict):
                    return return_class(value)
                elif isinstance(value, BaseModel):
                    return return_class(**value.model_dump())

        return value

    @staticmethod
    def _run_async_in_thread(coro) -> Any:
        """
        Run an asynchronous coroutine in a separate thread with its own event loop.

        Args:
            coro: The coroutine to execute.

        Returns:
            The result of the coroutine.

        Raises:
            Exception: Any exception raised by the coroutine.
        """
        result = None
        exception = None

        def target():
            nonlocal result, exception
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(coro)
            except Exception as e:
                exception = e
            finally:
                loop.close()

        thread = threading.Thread(target=target)
        thread.start()
        thread.join()

        if exception:
            raise exception
        return result

    def _run_async_fallback(self, command: Runnable, prepared_args: Any) -> Any:
        """
        Run async command with proper event loop handling.
        
        Args:
            command: The command to execute
            prepared_args: Prepared arguments for the command
            
        Returns:
            The result of the async command execution
        """
        async def run_async():
            return await command.ainvoke(prepared_args)

        try:
            _ = asyncio.get_running_loop()
            # If an event loop is running, use a separate thread
            return self._run_async_in_thread(run_async())
        except RuntimeError:
            # No event loop running, use asyncio.run
            return asyncio.run(run_async())

    def classify_command(self, command: Any) -> str:
        """
        Classify the type of command.

        Args:
            command: The command object to classify.

        Returns:
            str: The type of command ('graph', 'runnable', or 'other').
        """
        if isinstance(command, CompiledStateGraph):
            return "graph"
        elif isinstance(command, Runnable):
            return "runnable"
        elif isinstance(command, type) and issubclass(command, Runnable):
            return "runnable"
        return "other"

    async def execute_async(
        self,
        command_name: str,
        args: Any,
        execution_context: Optional[ExecutionContext] = None,
    ) -> Any:
        """
        Execute a command asynchronously with a synchronous fallback.

        Args:
            command_name: The name of the command to execute.
            args: The arguments to pass to the command.
            execution_context: Optional execution context to inject if command supports it.

        Returns:
            The result of the command execution.

        Raises:
            ValueError: If the command supports neither async nor sync execution.
        """
        import time
        start_time = time.time()
        
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()

        # Prepare arguments with execution context if needed
        prepared_args = self._prepare_command_args(command, args, execution_context)

        try:
            result = await command.ainvoke(prepared_args)
        except TypeError as e:
            # Fall back to sync execution if async is not supported
            error_msg = str(e).lower()
            if (
                "async not supported" in error_msg
                or "synchronous" in error_msg
                or "ainvoke" in error_msg
            ):
                # Fallback to sync execution
                result = command.invoke(prepared_args)
            else:
                raise  # Re-raise unexpected TypeErrors
        
        result = self._fix_return_type(return_class, result)
        
        # Calculate execution time and populate CommandOutput if applicable
        execution_time = time.time() - start_time
        result = self._populate_command_output(result, execution_context, execution_time)
        
        return result

    def execute_sync(
        self,
        command_name: str,
        args: Any,
        execution_context: Optional[ExecutionContext] = None,
    ) -> Any:
        """
        Execute a command synchronously with an enhanced async fallback.

        Args:
            command_name: The name of the command to execute.
            args: The arguments to pass to the command.
            execution_context: Optional execution context to inject if command supports it.

        Returns:
            The result of the command execution.

        Raises:
            ValueError: If the command has no valid implementation.
            TypeError: For unexpected type errors not related to missing sync implementation.
        """
        import time
        start_time = time.time()
        
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()

        # Parse input to correct format
        parsed_args = self.parse_input(command, args)

        # Prepare arguments with execution context if needed
        prepared_args = self._prepare_command_args(
            command, parsed_args, execution_context
        )

        try:
            # Try synchronous execution first
            result = command.invoke(prepared_args)
            result = self._fix_return_type(return_class, result)
        except TypeError as e:
            error_msg = str(e).lower()
            # Check for various async-related error messages from LangChain
            if (
                "synchronous" not in error_msg
                and "ainvoke" not in error_msg
                and "coroutine" not in error_msg
            ):
                raise  # Re-raise unexpected TypeErrors

            # Fallback to async execution
            result = self._run_async_fallback(command, prepared_args)
            result = self._fix_return_type(return_class, result)
        except AttributeError:
            # Handle case where invoke doesn't exist, try async
            try:
                result = self._run_async_fallback(command, prepared_args)
                result = self._fix_return_type(return_class, result)
            except AttributeError:
                raise ValueError(
                    f"Command {command_name} supports neither sync nor async execution"
                )
        
        # Calculate execution time and populate CommandOutput if applicable
        execution_time = time.time() - start_time
        result = self._populate_command_output(result, execution_context, execution_time)
        
        return result

    async def stream_async(
        self,
        command_name: str,
        args: Any,
        execution_context: Optional[ExecutionContext] = None,
    ) -> AsyncIterator:
        """
        Stream results from a command asynchronously with fallbacks.

        Args:
            command_name: The name of the command to stream.
            args: The arguments to pass to the command.
            execution_context: Optional execution context to inject if command supports it.

        Yields:
            The streamed chunks, properly typed.
        """
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()

        # Prepare arguments with execution context if needed
        prepared_args = self._prepare_command_args(command, args, execution_context)

        try:
            async for chunk in command.astream(prepared_args):
                yield self._fix_return_type(return_class, chunk)
        except (TypeError, AttributeError):
            try:
                for chunk in command.stream(prepared_args):
                    yield self._fix_return_type(return_class, chunk)
            except AttributeError:
                result = await self.execute_async(
                    command_name, prepared_args, execution_context
                )
                yield result

    def stream_sync(
        self,
        command_name: str,
        args: Any,
        execution_context: Optional[ExecutionContext] = None,
    ) -> Iterator:
        """
        Stream results from a command synchronously with an async fallback.

        Args:
            command_name: The name of the command to stream.
            args: The arguments to pass to the command.
            execution_context: Optional execution context to inject if command supports it.

        Returns:
            An iterator over the streamed chunks.

        Raises:
            TypeError: For unexpected type errors not related to streaming support.
            AttributeError: If neither sync nor async streaming is supported.
        """
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()

        # Prepare arguments with execution context if needed
        prepared_args = self._prepare_command_args(command, args, execution_context)

        def sync_stream_generator():
            try:
                # Attempt synchronous streaming
                for chunk in command.stream(prepared_args):
                    yield self._fix_return_type(return_class, chunk)
            except (TypeError, AttributeError) as e:
                # Check if the error is due to lack of synchronous support or missing stream method
                if (
                    "No synchronous function provided" in str(e)
                    or "stream" in str(e)
                    or isinstance(e, AttributeError)
                ):
                    # Fallback to async streaming
                    async def collect_async_stream():
                        return [
                            chunk
                            async for chunk in self.stream_async(
                                command_name, prepared_args, execution_context
                            )
                        ]

                    # Run async code based on whether there's an active event loop
                    try:
                        _ = asyncio.get_running_loop()
                        chunks = self._run_async_in_thread(collect_async_stream())
                    except RuntimeError:
                        chunks = asyncio.run(collect_async_stream())

                    # Yield the collected chunks
                    for chunk in chunks:
                        yield chunk
                else:
                    raise  # Re-raise other errors that we don't handle

        try:
            return sync_stream_generator()
        except AttributeError:
            # Handle case where stream method doesn't exist at all
            async def collect_async_stream():
                return [
                    chunk
                    async for chunk in self.stream_async(
                        command_name, prepared_args, execution_context
                    )
                ]

            try:
                _ = asyncio.get_running_loop()
                chunks = self._run_async_in_thread(collect_async_stream())
            except RuntimeError:
                chunks = asyncio.run(collect_async_stream())
            return iter(chunks)
