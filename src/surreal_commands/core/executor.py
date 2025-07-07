import asyncio
import threading
from typing import Any, AsyncIterator, Iterator

from langchain_core.runnables import Runnable
from langchain_core.runnables.utils import AddableDict
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel


class CommandExecutor:
    def __init__(self, command_dict: dict):
        """Initialize the CommandExecutor with a dictionary of commands."""
        self.command_dict = command_dict

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
        if hasattr(value, '__dict__') and hasattr(value, '__class__'):
            class_name = value.__class__.__name__
            if ('_output' in class_name.lower() or 'output' in class_name.lower()):
                # LangChain auto-generated schema object, convert to dict
                if hasattr(value, 'model_dump'):
                    # Pydantic model
                    value = value.model_dump()
                elif hasattr(value, '__dict__'):
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

    async def execute_async(self, command_name: str, args: Any) -> Any:
        """
        Execute a command asynchronously with a synchronous fallback.

        Args:
            command_name: The name of the command to execute.
            args: The arguments to pass to the command.

        Returns:
            The result of the command execution.

        Raises:
            ValueError: If the command supports neither async nor sync execution.
        """
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()

        try:
            result = await command.ainvoke(args)
        except (TypeError, AttributeError):
            try:
                result = command.invoke(args)
            except AttributeError:
                raise ValueError(
                    f"Command {command_name} supports neither async nor sync execution"
                )

        return self._fix_return_type(return_class, result)

    def execute_sync(self, command_name: str, args: Any) -> Any:
        """
        Execute a command synchronously with an enhanced async fallback.

        Args:
            command_name: The name of the command to execute.
            args: The arguments to pass to the command.

        Returns:
            The result of the command execution.

        Raises:
            ValueError: If the command has no valid implementation.
            TypeError: For unexpected type errors not related to missing sync implementation.
        """
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()
        
        # Parse input to correct format
        parsed_args = self.parse_input(command, args)

        try:
            # Try synchronous execution first
            result = command.invoke(parsed_args)
            return self._fix_return_type(return_class, result)
        except TypeError as e:
            error_msg = str(e).lower()
            # Check for various async-related error messages from LangChain
            if ("synchronous" not in error_msg and "ainvoke" not in error_msg and 
                "coroutine" not in error_msg):
                raise  # Re-raise unexpected TypeErrors

            # Fallback to async execution
            async def run_async():
                return await command.ainvoke(parsed_args)

            try:
                _ = asyncio.get_running_loop()
                # If an event loop is running, use a separate thread
                result = self._run_async_in_thread(run_async())
            except RuntimeError:
                # No event loop running, use asyncio.run
                result = asyncio.run(run_async())
            return self._fix_return_type(return_class, result)
        except AttributeError:
            # Handle case where invoke doesn't exist, try async
            try:
                async def run_async():
                    return await command.ainvoke(parsed_args)

                try:
                    _ = asyncio.get_running_loop()
                    result = self._run_async_in_thread(run_async())
                except RuntimeError:
                    result = asyncio.run(run_async())
                return self._fix_return_type(return_class, result)
            except AttributeError:
                raise ValueError(
                    f"Command {command_name} supports neither sync nor async execution"
                )

    async def stream_async(self, command_name: str, args: Any) -> AsyncIterator:
        """
        Stream results from a command asynchronously with fallbacks.

        Args:
            command_name: The name of the command to stream.
            args: The arguments to pass to the command.

        Yields:
            The streamed chunks, properly typed.
        """
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()

        try:
            async for chunk in command.astream(args):
                yield self._fix_return_type(return_class, chunk)
        except (TypeError, AttributeError):
            try:
                for chunk in command.stream(args):
                    yield self._fix_return_type(return_class, chunk)
            except AttributeError:
                result = await self.execute_async(command_name, args)
                yield result

    def stream_sync(self, command_name: str, args: Any) -> Iterator:
        """
        Stream results from a command synchronously with an async fallback.

        Args:
            command_name: The name of the command to stream.
            args: The arguments to pass to the command.

        Returns:
            An iterator over the streamed chunks.

        Raises:
            TypeError: For unexpected type errors not related to streaming support.
            AttributeError: If neither sync nor async streaming is supported.
        """
        command: Runnable = self.command_dict[command_name]
        return_class = getattr(command, "get_output_schema", lambda: Any)()

        def sync_stream_generator():
            try:
                # Attempt synchronous streaming
                for chunk in command.stream(args):
                    yield self._fix_return_type(return_class, chunk)
            except (TypeError, AttributeError) as e:
                # Check if the error is due to lack of synchronous support or missing stream method
                if ("No synchronous function provided" in str(e) or 
                    "stream" in str(e) or isinstance(e, AttributeError)):
                    # Fallback to async streaming
                    async def collect_async_stream():
                        return [
                            chunk
                            async for chunk in self.stream_async(command_name, args)
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
                return [chunk async for chunk in self.stream_async(command_name, args)]

            try:
                _ = asyncio.get_running_loop()
                chunks = self._run_async_in_thread(collect_async_stream())
            except RuntimeError:
                chunks = asyncio.run(collect_async_stream())
            return iter(chunks)
