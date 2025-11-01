"""Integration tests for retry functionality."""

import pytest
from unittest.mock import patch
from pydantic import BaseModel

from src.surreal_commands import command, RetryConfig, RetryStrategy
from src.surreal_commands.core.registry import registry
from src.surreal_commands.core.service import CommandService


class CommandInput(BaseModel):
    """Command input model."""

    value: str


class CommandOutput(BaseModel):
    """Command output model."""

    result: str


# Counter for tracking attempts
attempt_counter = {"count": 0}


@pytest.fixture(autouse=True)
def reset_attempt_counter():
    """Reset attempt counter before each test."""
    attempt_counter["count"] = 0
    yield
    attempt_counter["count"] = 0


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before each test."""
    registry._items.clear()
    registry._commands.clear()
    registry._apps.clear()
    yield
    registry._items.clear()
    registry._commands.clear()
    registry._apps.clear()


class TestRetryIntegration:
    """Test retry integration with command execution."""

    def test_command_without_retry(self):
        """Test command registration without retry config."""

        @command("no_retry_cmd", app="test_retry")
        def no_retry_cmd(input_data: CommandInput) -> CommandOutput:
            return CommandOutput(result=f"Processed: {input_data.value}")

        item = registry.get_command_by_id("test_retry.no_retry_cmd")
        assert item is not None
        assert item.retry_config is None

    def test_command_with_retry_dict(self):
        """Test command registration with retry config as dict."""

        @command(
            "retry_cmd",
            app="test",
            retry={"max_attempts": 5, "wait_strategy": "fixed", "wait_time": 0.1},
        )
        def retry_cmd(input_data: CommandInput) -> CommandOutput:
            return CommandOutput(result=f"Processed: {input_data.value}")

        item = registry.get_command_by_id("test.retry_cmd")
        assert item is not None
        assert item.retry_config is not None
        assert item.retry_config.max_attempts == 5
        assert item.retry_config.wait_strategy == RetryStrategy.FIXED
        assert item.retry_config.wait_time == 0.1

    def test_command_with_retry_config_object(self):
        """Test command registration with RetryConfig object."""
        config = RetryConfig(max_attempts=3, wait_strategy=RetryStrategy.EXPONENTIAL)

        @command("retry_obj_cmd", app="test", retry=config)
        def retry_obj_cmd(input_data: CommandInput) -> CommandOutput:
            return CommandOutput(result=f"Processed: {input_data.value}")

        item = registry.get_command_by_id("test.retry_obj_cmd")
        assert item is not None
        assert item.retry_config is not None
        assert item.retry_config.max_attempts == 3

    def test_command_with_retry_disabled(self):
        """Test command with retry explicitly disabled."""

        @command("disabled_cmd", app="test", retry={"enabled": False})
        def disabled_cmd(input_data: CommandInput) -> CommandOutput:
            return CommandOutput(result=f"Processed: {input_data.value}")

        item = registry.get_command_by_id("test.disabled_cmd")
        assert item is not None
        assert item.retry_config is None

    @pytest.mark.asyncio
    async def test_successful_execution_no_retry_needed(self):
        """Test successful execution that doesn't need retry."""

        @command("success_cmd", app="test", retry={"max_attempts": 3})
        def success_cmd(input_data: CommandInput) -> CommandOutput:
            attempt_counter["count"] += 1
            return CommandOutput(result=f"Success: {input_data.value}")

        service = CommandService()
        input_data = {"value": "test"}

        # Mock database operations
        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.success_cmd",
                input_data=input_data,
            )

        assert result.result == "Success: test"
        assert attempt_counter["count"] == 1  # Only executed once

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        """Test retry behavior when command fails then succeeds."""

        @command(
            "flaky_cmd",
            app="test",
            retry={"max_attempts": 3, "wait_strategy": "fixed", "wait_time": 0.01},
        )
        def flaky_cmd(input_data: CommandInput) -> CommandOutput:
            attempt_counter["count"] += 1
            if attempt_counter["count"] < 3:
                raise ValueError(f"Attempt {attempt_counter['count']} failed")
            return CommandOutput(result=f"Success on attempt {attempt_counter['count']}")

        service = CommandService()
        input_data = {"value": "test"}

        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.flaky_cmd",
                input_data=input_data,
            )

        assert result.result == "Success on attempt 3"
        assert attempt_counter["count"] == 3  # Retried twice, succeeded on third

    @pytest.mark.asyncio
    async def test_retry_exhausted_all_attempts(self):
        """Test when all retry attempts are exhausted."""

        @command(
            "always_fail_cmd",
            app="test",
            retry={"max_attempts": 2, "wait_strategy": "fixed", "wait_time": 0.01},
        )
        def always_fail_cmd(input_data: CommandInput) -> CommandOutput:
            attempt_counter["count"] += 1
            raise RuntimeError(f"Always fails, attempt {attempt_counter['count']}")

        service = CommandService()
        input_data = {"value": "test"}

        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.always_fail_cmd",
                input_data=input_data,
            )

        # Command should have failed after all attempts
        assert result is None
        assert attempt_counter["count"] == 2  # Tried max_attempts times

    @pytest.mark.asyncio
    async def test_no_retry_on_failure(self):
        """Test command without retry config fails immediately."""

        @command("no_retry_fail_cmd", app="test")
        def no_retry_fail_cmd(input_data: CommandInput) -> CommandOutput:
            attempt_counter["count"] += 1
            raise RuntimeError("Command failed")

        service = CommandService()
        input_data = {"value": "test"}

        with patch.object(service, "update_command_result", return_value=None):
            result = await service.execute_command(
                command_id="test:123",
                command_name="test.no_retry_fail_cmd",
                input_data=input_data,
            )

        assert result is None
        assert attempt_counter["count"] == 1  # Only tried once, no retries
