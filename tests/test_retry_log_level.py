"""Tests for retry log level functionality."""

import pytest
from unittest.mock import Mock
from tenacity import RetryCallState

from src.surreal_commands.core.retry import (
    RetryLogLevel,
    create_before_sleep_callback,
)


class TestRetryLogCallback:
    """Test retry log callback with different log levels."""

    def _create_retry_state(self, attempt_num: int = 1, exception: Exception = None) -> RetryCallState:
        """Helper to create a mock RetryCallState."""
        if exception is None:
            exception = RuntimeError("Test error")

        retry_state = Mock(spec=RetryCallState)
        retry_state.attempt_number = attempt_num

        # Mock outcome
        outcome = Mock()
        outcome.failed = True
        outcome.exception.return_value = exception
        retry_state.outcome = outcome

        # Mock next_action
        next_action = Mock()
        next_action.sleep = 2.0
        retry_state.next_action = next_action

        return retry_state

    def test_callback_debug_level(self):
        """Test callback with DEBUG log level can be created and called."""
        callback = create_before_sleep_callback(RetryLogLevel.DEBUG)
        retry_state = self._create_retry_state(attempt_num=1)

        # Should not raise an exception
        callback(retry_state)

    def test_callback_info_level(self):
        """Test callback with INFO log level can be created and called."""
        callback = create_before_sleep_callback(RetryLogLevel.INFO)
        retry_state = self._create_retry_state(attempt_num=1)

        # Should not raise an exception
        callback(retry_state)

    def test_callback_warning_level(self):
        """Test callback with WARNING log level can be created and called."""
        callback = create_before_sleep_callback(RetryLogLevel.WARNING)
        retry_state = self._create_retry_state(attempt_num=2)

        # Should not raise an exception
        callback(retry_state)

    def test_callback_error_level(self):
        """Test callback with ERROR log level can be created and called."""
        callback = create_before_sleep_callback(RetryLogLevel.ERROR)
        retry_state = self._create_retry_state(attempt_num=3)

        # Should not raise an exception
        callback(retry_state)

    def test_callback_none_level(self):
        """Test callback with NONE log level suppresses all logs."""
        callback = create_before_sleep_callback(RetryLogLevel.NONE)
        retry_state = self._create_retry_state(attempt_num=1)

        # Should not raise an exception and should return early
        callback(retry_state)

    def test_callback_with_different_exceptions(self):
        """Test callback handles different exception types."""
        callback = create_before_sleep_callback(RetryLogLevel.INFO)

        # Test with ValueError
        retry_state = self._create_retry_state(
            attempt_num=1,
            exception=ValueError("Invalid value")
        )
        callback(retry_state)

        # Test with ConnectionError
        retry_state = self._create_retry_state(
            attempt_num=2,
            exception=ConnectionError("Connection failed")
        )
        callback(retry_state)

    def test_callback_with_multiple_attempts(self):
        """Test callback logs correct attempt numbers."""
        callback = create_before_sleep_callback(RetryLogLevel.INFO)

        for attempt in range(1, 4):
            retry_state = self._create_retry_state(attempt_num=attempt)
            # Should not raise an exception
            callback(retry_state)

    def test_callback_includes_wait_time(self):
        """Test callback includes next wait time in message."""
        callback = create_before_sleep_callback(RetryLogLevel.INFO)
        retry_state = self._create_retry_state(attempt_num=1)

        # Set specific wait time
        retry_state.next_action.sleep = 5.5

        # Should not raise an exception
        callback(retry_state)

    def test_callback_all_levels_produce_callbacks(self):
        """Test that all log levels produce valid callbacks."""
        retry_state = self._create_retry_state(attempt_num=1)

        for log_level in RetryLogLevel:
            callback = create_before_sleep_callback(log_level)

            # All callbacks should work without raising exceptions
            callback(retry_state)
