"""
Examples demonstrating retry functionality in surreal-commands.

Run this file to see various retry scenarios in action.
"""

from pydantic import BaseModel
from surreal_commands import command, RetryConfig, RetryStrategy


# Define input/output models
class ProcessInput(BaseModel):
    message: str
    fail_count: int = 0


class ProcessOutput(BaseModel):
    result: str
    attempts: int


# Track attempts for demonstration
attempt_counters = {}


# Example 1: Basic retry with fixed wait time
@command(
    "basic_retry",
    app="examples",
    retry={"max_attempts": 3, "wait_strategy": "fixed", "wait_time": 1},
)
def basic_retry_example(input_data: ProcessInput) -> ProcessOutput:
    """
    Example: Basic retry with 3 attempts and 1 second fixed wait between retries.
    """
    cmd_id = "basic_retry"
    attempt_counters[cmd_id] = attempt_counters.get(cmd_id, 0) + 1

    if attempt_counters[cmd_id] < input_data.fail_count:
        raise RuntimeError(
            f"Simulated failure on attempt {attempt_counters[cmd_id]}"
        )

    return ProcessOutput(
        result=f"Success: {input_data.message}",
        attempts=attempt_counters[cmd_id],
    )


# Example 2: Exponential backoff (recommended for network calls)
@command(
    "network_retry",
    app="examples",
    retry={
        "max_attempts": 5,
        "wait_strategy": "exponential",
        "wait_min": 1,
        "wait_max": 60,
        "wait_multiplier": 2,
    },
)
def network_retry_example(input_data: ProcessInput) -> ProcessOutput:
    """
    Example: Exponential backoff for network calls.
    Wait times: 1s, 2s, 4s, 8s, 16s (capped at 60s)
    """
    cmd_id = "network_retry"
    attempt_counters[cmd_id] = attempt_counters.get(cmd_id, 0) + 1

    if attempt_counters[cmd_id] < input_data.fail_count:
        raise ConnectionError(
            f"Network error on attempt {attempt_counters[cmd_id]}"
        )

    return ProcessOutput(
        result=f"Network call succeeded: {input_data.message}",
        attempts=attempt_counters[cmd_id],
    )


# Example 3: Retry only on specific exceptions
@command(
    "selective_retry",
    app="examples",
    retry={
        "max_attempts": 3,
        "wait_strategy": "fixed",
        "wait_time": 0.5,
        "retry_on": [ConnectionError, TimeoutError],
    },
)
def selective_retry_example(input_data: ProcessInput) -> ProcessOutput:
    """
    Example: Retry only on ConnectionError and TimeoutError.
    Other exceptions will fail immediately without retry.
    """
    cmd_id = "selective_retry"
    attempt_counters[cmd_id] = attempt_counters.get(cmd_id, 0) + 1

    if attempt_counters[cmd_id] < input_data.fail_count:
        # This will be retried
        raise ConnectionError(
            f"Connection failed on attempt {attempt_counters[cmd_id]}"
        )

    return ProcessOutput(
        result=f"Connection successful: {input_data.message}",
        attempts=attempt_counters[cmd_id],
    )


# Example 4: Avoid retrying on permanent errors
@command(
    "avoid_permanent_errors",
    app="examples",
    retry={
        "max_attempts": 3,
        "wait_strategy": "exponential",
        "stop_on": [ValueError, TypeError, KeyError],
    },
)
def avoid_permanent_errors_example(input_data: ProcessInput) -> ProcessOutput:
    """
    Example: Don't retry on permanent errors (validation, type, key errors).
    These errors won't be fixed by retrying.
    """
    cmd_id = "avoid_permanent"
    attempt_counters[cmd_id] = attempt_counters.get(cmd_id, 0) + 1

    if attempt_counters[cmd_id] < input_data.fail_count:
        # RuntimeError will be retried, but ValueError won't
        raise RuntimeError(
            f"Transient error on attempt {attempt_counters[cmd_id]}"
        )

    return ProcessOutput(
        result=f"Processing completed: {input_data.message}",
        attempts=attempt_counters[cmd_id],
    )


# Example 5: No retry (explicitly disabled)
@command("no_retry", app="examples", retry=None)
def no_retry_example(input_data: ProcessInput) -> ProcessOutput:
    """
    Example: Command with retry explicitly disabled.
    Fails immediately on first error.
    """
    cmd_id = "no_retry"
    attempt_counters[cmd_id] = attempt_counters.get(cmd_id, 0) + 1

    if input_data.fail_count > 0:
        raise RuntimeError("Fails immediately without retry")

    return ProcessOutput(
        result=f"Completed without retry: {input_data.message}",
        attempts=attempt_counters[cmd_id],
    )


# Example 6: Using RetryConfig object
retry_config = RetryConfig(
    enabled=True,
    max_attempts=4,
    wait_strategy=RetryStrategy.EXPONENTIAL_JITTER,
    wait_min=1,
    wait_max=30,
)


@command("config_object", app="examples", retry=retry_config)
def config_object_example(input_data: ProcessInput) -> ProcessOutput:
    """
    Example: Using RetryConfig object for type-safe configuration.
    Includes exponential backoff with random jitter to prevent thundering herd.
    """
    cmd_id = "config_object"
    attempt_counters[cmd_id] = attempt_counters.get(cmd_id, 0) + 1

    if attempt_counters[cmd_id] < input_data.fail_count:
        raise RuntimeError(
            f"Error with jitter on attempt {attempt_counters[cmd_id]}"
        )

    return ProcessOutput(
        result=f"Success with RetryConfig: {input_data.message}",
        attempts=attempt_counters[cmd_id],
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Surreal Commands - Retry Examples")
    print("=" * 60)
    print()
    print("This file demonstrates various retry configurations.")
    print("Examples are registered and ready to use with surreal-commands.")
    print()
    print("Examples included:")
    print("1. basic_retry - Fixed wait time between retries")
    print("2. network_retry - Exponential backoff for network calls")
    print("3. selective_retry - Retry only specific exceptions")
    print("4. avoid_permanent_errors - Skip retrying permanent errors")
    print("5. no_retry - Explicitly disable retries")
    print("6. config_object - Using RetryConfig for type safety")
    print()
    print("To use these examples:")
    print("1. Start SurrealDB: docker run -p 8000:8000 surrealdb/surrealdb:latest start")
    print("2. Start worker: surreal-commands-worker --import-modules examples.retry_examples")
    print("3. Submit commands using the API")
    print()
