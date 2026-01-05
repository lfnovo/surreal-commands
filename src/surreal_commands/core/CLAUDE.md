# Core

Command execution engine - registry, service, executor, worker, client API, and retry logic.

## Files

- **`types.py`**: Type definitions - `ExecutionContext` (dataclass), `CommandInput`/`CommandOutput` (Pydantic bases), `CommandRegistryItem`
- **`registry.py`**: Singleton `CommandRegistry` - stores commands as LangChain Runnables by `app.name`
- **`service.py`**: `CommandService` - command lifecycle (submit, execute, update status)
- **`executor.py`**: `CommandExecutor` - execution engine with sync/async handling, context injection, type coercion
- **`worker.py`**: Worker process - polls SurrealDB via LIVE query, executes commands concurrently
- **`client.py`**: Public API - `submit_command()`, `wait_for_command()`, `get_command_status()`
- **`retry.py`**: Retry configuration and tenacity integration - strategies, config merging, instance builders

## Patterns

- **Singleton Registry**: `registry` is a global singleton - import and use directly
- **LangChain Runnables**: All commands wrapped in `RunnableLambda` - supports `invoke`/`ainvoke`
- **Context Injection**: Commands using `CommandInput` get `ExecutionContext` injected automatically
- **Output Population**: Commands returning `CommandOutput` get `command_id`, `execution_time` auto-populated
- **Lazy Initialization**: `CommandService.executor` created on first access (after all commands registered)
- **Semaphore Concurrency**: Worker uses `asyncio.Semaphore` for max concurrent tasks

## Integration

- Imports from: `repository`, `langchain_core.runnables`, `tenacity`, `surrealdb`
- Used by: `decorators.py`, `cli/`, root `__init__.py`
- Flow: `@command` decorator -> `registry.register()` -> queue via `CommandService` -> `Worker` -> `CommandExecutor`

## Gotchas

- **Registry is memory-only**: Commands must be imported before worker starts (use `--import-modules`)
- **Executor caching**: Signature inspection cached per command object ID - 100 entry limit
- **Async fallback**: `execute_sync()` runs async commands in new thread with fresh event loop
- **RetryError**: On exhausted retries, `tenacity.RetryError` raised with `.last_attempt.exception()` for original error
- **Forward reference**: `CommandRegistryItem.model_rebuild()` called in root `__init__.py` to resolve `RetryConfig` type

## When Adding Code

- Commands inherit from `CommandInput` for context access, `CommandOutput` for auto-populated metadata
- Use `@command(name, app=None, retry=None)` decorator - app auto-detected from module
- Status values: `new`, `running`, `completed`, `failed`, `canceled`
- Retry config merges: per-command overrides global env config

## Command Execution Flow

```
@command decorator
    -> RunnableLambda wrapping function
    -> registry.register(app, name, runnable, retry_config)

submit_command(app, name, args)
    -> CommandService.submit_command_sync()
    -> creates SurrealDB record with status="new"
    -> returns command_id

Worker (LIVE query on command table)
    -> picks up status="new" commands
    -> CommandService.execute_command()
        -> sets status="running"
        -> CommandExecutor.execute_async()
            -> injects ExecutionContext
            -> invokes runnable
            -> populates CommandOutput fields
        -> retry logic (if enabled)
        -> sets status="completed" or "failed"
```

## Retry Configuration

```python
# Per-command with log level control
@command("name", retry={
    "max_attempts": 3,
    "wait_strategy": "exponential",
    "retry_log_level": "debug"  # Control retry log verbosity
})

# Global (env vars)
SURREAL_COMMANDS_RETRY_ENABLED=true
SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS=3
SURREAL_COMMANDS_RETRY_WAIT_STRATEGY=exponential
SURREAL_COMMANDS_RETRY_LOG_LEVEL=info

# Strategies: fixed, exponential, random, exponential_jitter
# Log Levels: debug, info (default), warning, error, none
```
