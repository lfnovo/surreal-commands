"""Tests for exception filtering in retry logic."""

import pytest
from pydantic import BaseModel, ValidationError

from src.surreal_commands import command
from src.surreal_commands.core.registry import registry
from src.surreal_commands.core.service import CommandService
from unittest.mock import patch


class TestInput(BaseModel):
    """Test input model."""

    value: str


class TestOutput(BaseModel):
    """Test output model."""

    result: str


# Custom exceptions for testing
class TransientError(Exception):
    """Simulates a transient error that should be retried."""

    pass


class PermanentError(Exception):
    """Simulates a permanent error that should not be retried."""

    pass


attempt_counter = {"count": 0, "exceptions": []}


@pytest.fixture(autouse=True)
def reset_counters():
    """Reset counters before each test."""
    attempt_counter["count"] = 0
    attempt_counter["exceptions"] = []
    yield
    attempt_counter["count"] = 0
    attempt_counter["exceptions"] = []


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    registry._items.clear()
    registry._commands.clear()
    registry._apps.clear()
    yield


class TestExceptionFiltering:
    """Test exception filtering in retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_specific_exception(self):
        """Test retrying only on specific exception types."""

        @command(
            "retry_on_transient",
            app="test",
            retry={
                "max_attempts": 3,
                "wait_strategy": "fixed",
                "wait_time": 0.01,
                "retry_on": [TransientError],
            },
        )
        def retry_on_transient(input_data: TestInput) -> TestOutput:
            attempt_counter["count"] += 1
            if attempt_counter["count"] < 2:
                raise TransientError("Transient failure")
            return TestOutput(result="Success")

        service = CommandService()
        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.retry_on_transient",
                input_data={"value": "test"},
            )

        assert result.result == "Success"
        assert attempt_counter["count"] == 2  # Retried once

    @pytest.mark.asyncio
    async def test_stop_on_specific_exception(self):
        """Test not retrying on specific exception types."""

        @command(
            "stop_on_permanent",
            app="test",
            retry={
                "max_attempts": 3,
                "wait_strategy": "fixed",
                "wait_time": 0.01,
                "stop_on": [ValidationError, PermanentError],
            },
        )
        def stop_on_permanent(input_data: TestInput) -> TestOutput:
            attempt_counter["count"] += 1
            if attempt_counter["count"] == 1:
                raise PermanentError("Permanent failure - should not retry")
            return TestOutput(result="Should not reach here")

        service = CommandService()
        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.stop_on_permanent",
                input_data={"value": "test"},
            )

        assert result is None  # Command failed
        assert attempt_counter["count"] == 1  # Should not have retried

    @pytest.mark.asyncio
    async def test_retry_on_multiple_exceptions(self):
        """Test retrying on multiple exception types."""

        @command(
            "retry_multiple",
            app="test",
            retry={
                "max_attempts": 4,
                "wait_strategy": "fixed",
                "wait_time": 0.01,
                "retry_on": [TransientError, RuntimeError, ConnectionError],
            },
        )
        def retry_multiple(input_data: TestInput) -> TestOutput:
            attempt_counter["count"] += 1
            if attempt_counter["count"] == 1:
                exc = TransientError("First attempt")
            elif attempt_counter["count"] == 2:
                exc = RuntimeError("Second attempt")
            elif attempt_counter["count"] == 3:
                exc = ConnectionError("Third attempt")
            else:
                return TestOutput(result="Success on attempt 4")

            attempt_counter["exceptions"].append(type(exc).__name__)
            raise exc

        service = CommandService()
        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.retry_multiple",
                input_data={"value": "test"},
            )

        assert result.result == "Success on attempt 4"
        assert attempt_counter["count"] == 4
        assert attempt_counter["exceptions"] == [
            "TransientError",
            "RuntimeError",
            "ConnectionError",
        ]

    @pytest.mark.asyncio
    async def test_no_exception_filter_retries_all(self):
        """Test that without exception filters, all exceptions are retried."""

        @command(
            "retry_all",
            app="test",
            retry={"max_attempts": 3, "wait_strategy": "fixed", "wait_time": 0.01},
        )
        def retry_all(input_data: TestInput) -> TestOutput:
            attempt_counter["count"] += 1
            if attempt_counter["count"] < 3:
                # Different exceptions on each attempt
                if attempt_counter["count"] == 1:
                    raise ValueError("Value error")
                else:
                    raise TypeError("Type error")
            return TestOutput(result="Success")

        service = CommandService()
        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.retry_all",
                input_data={"value": "test"},
            )

        assert result.result == "Success"
        assert attempt_counter["count"] == 3  # Retried on all exception types
