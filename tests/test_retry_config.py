"""Tests for retry configuration."""

import pytest
from pydantic import ValidationError

from src.surreal_commands.core.retry import (
    RetryConfig,
    RetryLogLevel,
    RetryStrategy,
    get_global_retry_config,
    merge_retry_configs,
)


class TestRetryConfig:
    """Test RetryConfig model."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.enabled is True
        assert config.max_attempts == 3
        assert config.wait_strategy == RetryStrategy.EXPONENTIAL
        assert config.wait_time == 1.0
        assert config.wait_min == 1.0
        assert config.wait_max == 60.0
        assert config.wait_multiplier == 2.0
        assert config.retry_on is None
        assert config.stop_on is None
        assert config.retry_log_level == RetryLogLevel.INFO

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            enabled=True,
            max_attempts=5,
            wait_strategy=RetryStrategy.FIXED,
            wait_time=2.0,
        )
        assert config.enabled is True
        assert config.max_attempts == 5
        assert config.wait_strategy == RetryStrategy.FIXED
        assert config.wait_time == 2.0

    def test_disabled_config(self):
        """Test disabled retry configuration."""
        config = RetryConfig(enabled=False)
        assert config.enabled is False

    def test_dict_creation(self):
        """Test creating RetryConfig from dict."""
        config_dict = {
            "max_attempts": 4,
            "wait_strategy": "fixed",
            "wait_time": 3.0,
        }
        config = RetryConfig(**config_dict)
        assert config.max_attempts == 4
        assert config.wait_strategy == RetryStrategy.FIXED
        assert config.wait_time == 3.0

    def test_invalid_max_attempts(self):
        """Test validation for max_attempts."""
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=0)

    def test_invalid_wait_max_less_than_wait_min(self):
        """Test validation for wait_max < wait_min."""
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(wait_min=10.0, wait_max=5.0)
        assert "wait_max" in str(exc_info.value)
        assert "wait_min" in str(exc_info.value)

    def test_valid_wait_max_equals_wait_min(self):
        """Test that wait_max == wait_min is valid."""
        config = RetryConfig(wait_min=5.0, wait_max=5.0)
        assert config.wait_min == 5.0
        assert config.wait_max == 5.0

    def test_all_wait_strategies(self):
        """Test all wait strategies."""
        for strategy in RetryStrategy:
            config = RetryConfig(wait_strategy=strategy)
            assert config.wait_strategy == strategy

    def test_default_retry_log_level(self):
        """Test default retry log level is INFO."""
        config = RetryConfig()
        assert config.retry_log_level == RetryLogLevel.INFO

    def test_custom_retry_log_level(self):
        """Test custom retry log level."""
        config = RetryConfig(retry_log_level=RetryLogLevel.DEBUG)
        assert config.retry_log_level == RetryLogLevel.DEBUG

        config = RetryConfig(retry_log_level=RetryLogLevel.WARNING)
        assert config.retry_log_level == RetryLogLevel.WARNING

        config = RetryConfig(retry_log_level=RetryLogLevel.ERROR)
        assert config.retry_log_level == RetryLogLevel.ERROR

        config = RetryConfig(retry_log_level=RetryLogLevel.NONE)
        assert config.retry_log_level == RetryLogLevel.NONE

    def test_retry_log_level_from_string(self):
        """Test creating RetryConfig with string log level."""
        config = RetryConfig(retry_log_level="debug")
        assert config.retry_log_level == RetryLogLevel.DEBUG

        config = RetryConfig(retry_log_level="warning")
        assert config.retry_log_level == RetryLogLevel.WARNING

        config = RetryConfig(retry_log_level="none")
        assert config.retry_log_level == RetryLogLevel.NONE

    def test_all_retry_log_levels(self):
        """Test all retry log levels."""
        for log_level in RetryLogLevel:
            config = RetryConfig(retry_log_level=log_level)
            assert config.retry_log_level == log_level


class TestGlobalRetryConfig:
    """Test global retry configuration from environment variables."""

    def test_no_env_vars(self, monkeypatch):
        """Test when no environment variables are set."""
        monkeypatch.delenv("SURREAL_COMMANDS_RETRY_ENABLED", raising=False)
        config = get_global_retry_config()
        assert config is None

    def test_enabled_false(self, monkeypatch):
        """Test when retry is explicitly disabled."""
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_ENABLED", "false")
        config = get_global_retry_config()
        assert config is None

    def test_enabled_true(self, monkeypatch):
        """Test when retry is enabled."""
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_ENABLED", "true")
        config = get_global_retry_config()
        assert config is not None
        assert config.enabled is True

    def test_custom_max_attempts(self, monkeypatch):
        """Test custom max attempts from environment."""
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_ENABLED", "true")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS", "5")
        config = get_global_retry_config()
        assert config.max_attempts == 5

    def test_custom_wait_strategy(self, monkeypatch):
        """Test custom wait strategy from environment."""
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_ENABLED", "true")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_WAIT_STRATEGY", "fixed")
        config = get_global_retry_config()
        assert config.wait_strategy == RetryStrategy.FIXED

    def test_all_env_vars(self, monkeypatch):
        """Test all environment variables."""
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_ENABLED", "1")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS", "7")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_WAIT_STRATEGY", "exponential")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_WAIT_TIME", "2.5")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_WAIT_MIN", "0.5")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_WAIT_MAX", "30")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_WAIT_MULTIPLIER", "3")

        config = get_global_retry_config()
        assert config.enabled is True
        assert config.max_attempts == 7
        assert config.wait_strategy == RetryStrategy.EXPONENTIAL
        assert config.wait_time == 2.5
        assert config.wait_min == 0.5
        assert config.wait_max == 30.0
        assert config.wait_multiplier == 3.0

    def test_env_var_retry_log_level(self, monkeypatch):
        """Test retry log level from environment variable."""
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_ENABLED", "true")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_LOG_LEVEL", "debug")
        config = get_global_retry_config()
        assert config.retry_log_level == RetryLogLevel.DEBUG

        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_LOG_LEVEL", "warning")
        config = get_global_retry_config()
        assert config.retry_log_level == RetryLogLevel.WARNING

        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_LOG_LEVEL", "none")
        config = get_global_retry_config()
        assert config.retry_log_level == RetryLogLevel.NONE

    def test_env_var_invalid_retry_log_level(self, monkeypatch):
        """Test warning on invalid retry log level from environment."""
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_ENABLED", "true")
        monkeypatch.setenv("SURREAL_COMMANDS_RETRY_LOG_LEVEL", "invalid_level")

        config = get_global_retry_config()
        # Should still return config with default log level
        assert config is not None
        assert config.retry_log_level == RetryLogLevel.INFO


class TestMergeRetryConfigs:
    """Test merging retry configurations."""

    def test_no_configs(self):
        """Test when no configs are provided."""
        result = merge_retry_configs(None, None)
        assert result is None

    def test_only_global(self):
        """Test when only global config is provided."""
        global_config = RetryConfig(max_attempts=5)
        result = merge_retry_configs(global_config, None)
        assert result is not None
        assert result.max_attempts == 5

    def test_only_per_command(self):
        """Test when only per-command config is provided."""
        per_command = RetryConfig(max_attempts=7)
        result = merge_retry_configs(None, per_command)
        assert result is not None
        assert result.max_attempts == 7

    def test_per_command_overrides_global(self):
        """Test that per-command config overrides global."""
        global_config = RetryConfig(max_attempts=3, wait_time=2.0)
        per_command = RetryConfig(max_attempts=5, wait_time=1.0)
        result = merge_retry_configs(global_config, per_command)
        assert result is not None
        assert result.max_attempts == 5
        # Per-command wait_time should override global
        assert result.wait_time == 1.0

    def test_per_command_disabled(self):
        """Test when per-command config disables retry."""
        global_config = RetryConfig(enabled=True, max_attempts=5)
        per_command = RetryConfig(enabled=False)
        result = merge_retry_configs(global_config, per_command)
        assert result is None

    def test_global_disabled(self):
        """Test when global config disables retry."""
        global_config = RetryConfig(enabled=False)
        per_command = RetryConfig(enabled=True, max_attempts=5)
        result = merge_retry_configs(global_config, per_command)
        # Per-command enabled should take precedence
        assert result is not None
        assert result.enabled is True
