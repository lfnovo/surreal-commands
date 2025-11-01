"""Retry configuration and logic for command execution."""

import os
from enum import Enum
from typing import Any, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    wait_random,
)


class RetryStrategy(str, Enum):
    """Wait strategy for retry attempts."""

    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    RANDOM = "random"
    EXPONENTIAL_JITTER = "exponential_jitter"


class RetryConfig(BaseModel):
    """Configuration for command retry behavior.

    Attributes:
        enabled: Whether retry is enabled for this command
        max_attempts: Maximum number of retry attempts (including initial attempt)
        wait_strategy: Strategy for waiting between retries
        wait_time: Fixed wait time in seconds (for FIXED strategy)
        wait_min: Minimum wait time in seconds (for EXPONENTIAL and RANDOM)
        wait_max: Maximum wait time in seconds (for EXPONENTIAL and RANDOM)
        wait_multiplier: Multiplier for exponential backoff (for EXPONENTIAL)
        retry_on: List of exception types that should trigger retries (inclusion list)
        stop_on: List of exception types that should NOT trigger retries (exclusion list)
    """

    enabled: bool = Field(default=True, description="Whether retry is enabled")
    max_attempts: int = Field(default=3, ge=1, description="Maximum retry attempts")
    wait_strategy: RetryStrategy = Field(
        default=RetryStrategy.EXPONENTIAL, description="Wait strategy between retries"
    )
    wait_time: float = Field(default=1.0, ge=0, description="Fixed wait time in seconds")
    wait_min: float = Field(default=1.0, ge=0, description="Minimum wait time in seconds")
    wait_max: float = Field(default=60.0, ge=0, description="Maximum wait time in seconds")
    wait_multiplier: float = Field(default=2.0, ge=1, description="Exponential backoff multiplier")
    retry_on: Optional[List[Type[Exception]]] = Field(
        default=None, description="Exception types that should trigger retries"
    )
    stop_on: Optional[List[Type[Exception]]] = Field(
        default=None, description="Exception types that should NOT trigger retries"
    )

    class Config:
        arbitrary_types_allowed = True


def get_global_retry_config() -> Optional[RetryConfig]:
    """Get global retry configuration from environment variables.

    Environment variables:
        SURREAL_COMMANDS_RETRY_ENABLED: Enable/disable retries (default: false)
        SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS: Maximum retry attempts (default: 3)
        SURREAL_COMMANDS_RETRY_WAIT_STRATEGY: Wait strategy (default: exponential)
        SURREAL_COMMANDS_RETRY_WAIT_TIME: Fixed wait time in seconds (default: 1)
        SURREAL_COMMANDS_RETRY_WAIT_MIN: Minimum wait time in seconds (default: 1)
        SURREAL_COMMANDS_RETRY_WAIT_MAX: Maximum wait time in seconds (default: 60)
        SURREAL_COMMANDS_RETRY_WAIT_MULTIPLIER: Exponential backoff multiplier (default: 2)

    Returns:
        RetryConfig if any retry environment variables are set and enabled is True,
        None otherwise
    """
    # Check if retries are enabled globally
    enabled_str = os.environ.get("SURREAL_COMMANDS_RETRY_ENABLED", "false").lower()
    if enabled_str not in ("true", "1", "yes", "on"):
        return None

    # Build config from environment variables
    config_dict: dict[str, Any] = {"enabled": True}

    if max_attempts := os.environ.get("SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS"):
        try:
            config_dict["max_attempts"] = int(max_attempts)
        except ValueError:
            logger.warning(f"Invalid SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS: {max_attempts}")

    if wait_strategy := os.environ.get("SURREAL_COMMANDS_RETRY_WAIT_STRATEGY"):
        try:
            config_dict["wait_strategy"] = RetryStrategy(wait_strategy.lower())
        except ValueError:
            logger.warning(f"Invalid SURREAL_COMMANDS_RETRY_WAIT_STRATEGY: {wait_strategy}")

    if wait_time := os.environ.get("SURREAL_COMMANDS_RETRY_WAIT_TIME"):
        try:
            config_dict["wait_time"] = float(wait_time)
        except ValueError:
            logger.warning(f"Invalid SURREAL_COMMANDS_RETRY_WAIT_TIME: {wait_time}")

    if wait_min := os.environ.get("SURREAL_COMMANDS_RETRY_WAIT_MIN"):
        try:
            config_dict["wait_min"] = float(wait_min)
        except ValueError:
            logger.warning(f"Invalid SURREAL_COMMANDS_RETRY_WAIT_MIN: {wait_min}")

    if wait_max := os.environ.get("SURREAL_COMMANDS_RETRY_WAIT_MAX"):
        try:
            config_dict["wait_max"] = float(wait_max)
        except ValueError:
            logger.warning(f"Invalid SURREAL_COMMANDS_RETRY_WAIT_MAX: {wait_max}")

    if wait_multiplier := os.environ.get("SURREAL_COMMANDS_RETRY_WAIT_MULTIPLIER"):
        try:
            config_dict["wait_multiplier"] = float(wait_multiplier)
        except ValueError:
            logger.warning(f"Invalid SURREAL_COMMANDS_RETRY_WAIT_MULTIPLIER: {wait_multiplier}")

    return RetryConfig(**config_dict)


def _build_wait_strategy(config: RetryConfig):
    """Build tenacity wait strategy from RetryConfig.

    Args:
        config: Retry configuration

    Returns:
        Tenacity wait function
    """
    if config.wait_strategy == RetryStrategy.FIXED:
        return wait_fixed(config.wait_time)
    elif config.wait_strategy == RetryStrategy.EXPONENTIAL:
        return wait_exponential(
            multiplier=config.wait_multiplier,
            min=config.wait_min,
            max=config.wait_max,
        )
    elif config.wait_strategy == RetryStrategy.RANDOM:
        return wait_random(min=config.wait_min, max=config.wait_max)
    elif config.wait_strategy == RetryStrategy.EXPONENTIAL_JITTER:
        # Combine exponential backoff with random jitter
        return wait_exponential(
            multiplier=config.wait_multiplier,
            min=config.wait_min,
            max=config.wait_max,
        ) + wait_random(0, config.wait_time)
    else:
        # Default to exponential
        return wait_exponential(
            multiplier=config.wait_multiplier,
            min=config.wait_min,
            max=config.wait_max,
        )


def _build_retry_condition(config: RetryConfig):
    """Build tenacity retry condition from RetryConfig.

    Args:
        config: Retry configuration

    Returns:
        Tenacity retry condition or None
    """
    conditions = []

    # Add inclusion list (retry_on)
    if config.retry_on:
        for exc_type in config.retry_on:
            conditions.append(retry_if_exception_type(exc_type))

    # Add exclusion list (stop_on)
    if config.stop_on:
        for exc_type in config.stop_on:
            conditions.append(retry_if_not_exception_type(exc_type))

    # If no conditions specified, retry on all exceptions (default tenacity behavior)
    if not conditions:
        return None

    # Combine conditions with OR logic for retry_on, AND logic for stop_on
    if len(conditions) == 1:
        return conditions[0]

    # If we have both retry_on and stop_on, we need to combine them properly
    # retry_on uses OR (retry if ANY match), stop_on uses AND (don't retry if ALL match)
    def combined_condition(retry_state):
        # If we have retry_on, check if exception matches any
        if config.retry_on:
            matches_retry_on = any(
                retry_if_exception_type(exc_type)(retry_state) for exc_type in config.retry_on
            )
            if not matches_retry_on:
                return False

        # If we have stop_on, check if exception matches none
        if config.stop_on:
            matches_stop_on = any(
                not retry_if_not_exception_type(exc_type)(retry_state) for exc_type in config.stop_on
            )
            if matches_stop_on:
                return False

        return True

    return combined_condition


def before_sleep_log(retry_state: RetryCallState) -> None:
    """Callback function to log retry attempts.

    Args:
        retry_state: Tenacity retry state containing attempt information
    """
    attempt_num = retry_state.attempt_number
    if retry_state.outcome and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        exception_type = type(exception).__name__
        exception_msg = str(exception)
    else:
        exception_type = "Unknown"
        exception_msg = "Unknown error"

    # Calculate next wait time
    next_wait = 0.0
    if retry_state.next_action and retry_state.next_action.sleep:
        next_wait = retry_state.next_action.sleep

    # Log with appropriate level
    if attempt_num == 1:
        logger.info(
            f"[Retry] Attempt {attempt_num} failed with {exception_type}: {exception_msg}, "
            f"waiting {next_wait:.1f}s before retry {attempt_num + 1}"
        )
    else:
        logger.debug(
            f"[Retry] Attempt {attempt_num} failed with {exception_type}: {exception_msg}, "
            f"waiting {next_wait:.1f}s before retry {attempt_num + 1}"
        )


def build_async_retry_instance(config: RetryConfig) -> AsyncRetrying:
    """Build AsyncRetrying instance from RetryConfig.

    Args:
        config: Retry configuration

    Returns:
        Configured AsyncRetrying instance
    """
    kwargs = {
        "stop": stop_after_attempt(config.max_attempts),
        "wait": _build_wait_strategy(config),
        "before_sleep": before_sleep_log,
        "reraise": True,  # Re-raise the original exception after all attempts exhausted
    }

    # Add retry condition if specified
    retry_condition = _build_retry_condition(config)
    if retry_condition:
        kwargs["retry"] = retry_condition

    return AsyncRetrying(**kwargs)


def build_retry_instance(config: RetryConfig) -> Retrying:
    """Build Retrying instance from RetryConfig (for sync execution).

    Args:
        config: Retry configuration

    Returns:
        Configured Retrying instance
    """
    kwargs = {
        "stop": stop_after_attempt(config.max_attempts),
        "wait": _build_wait_strategy(config),
        "before_sleep": before_sleep_log,
        "reraise": True,  # Re-raise the original exception after all attempts exhausted
    }

    # Add retry condition if specified
    retry_condition = _build_retry_condition(config)
    if retry_condition:
        kwargs["retry"] = retry_condition

    return Retrying(**kwargs)


def merge_retry_configs(
    global_config: Optional[RetryConfig], per_command_config: Optional[RetryConfig]
) -> Optional[RetryConfig]:
    """Merge global and per-command retry configurations.

    Per-command config always takes precedence over global config.
    If per-command config has enabled=False, return None (no retries).

    Args:
        global_config: Global retry configuration from environment
        per_command_config: Per-command retry configuration from decorator

    Returns:
        Merged RetryConfig, or None if retries are disabled
    """
    # If no configs at all, return None (retries disabled by default)
    if not global_config and not per_command_config:
        return None

    # If per-command config explicitly disables retries, return None
    if per_command_config and not per_command_config.enabled:
        return None

    # If only per-command config exists, use it
    if per_command_config and not global_config:
        return per_command_config if per_command_config.enabled else None

    # If only global config exists, use it
    if global_config and not per_command_config:
        return global_config if global_config.enabled else None

    # Both configs exist - merge them (per-command overrides global)
    # Start with global config as base
    merged_dict = global_config.model_dump()

    # Override with per-command config values
    per_command_dict = per_command_config.model_dump()
    for key, value in per_command_dict.items():
        # Only override if per-command value is explicitly set (not None for optional fields)
        if value is not None:
            merged_dict[key] = value

    merged_config = RetryConfig(**merged_dict)
    return merged_config if merged_config.enabled else None
