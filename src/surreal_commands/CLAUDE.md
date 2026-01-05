# Surreal Commands

Distributed task queue library using SurrealDB and LangChain Runnables.

## Submodules

- **[core/](core/CLAUDE.md)**: Command execution engine (registry, service, executor, worker, client, retry)
- **[cli/](cli/CLAUDE.md)**: Command-line tools (worker, dashboard, logs)
- **[repository/](repository/CLAUDE.md)**: SurrealDB connection and query utilities

See child CLAUDE.md files for implementation details.

## Files

- **`__init__.py`**: Public API exports - all primary interfaces exposed here
- **`decorators.py`**: `@command` decorator for registering functions as commands

## Public API

```python
# Command Registration
from surreal_commands import command, registry

# Command Execution & Monitoring
from surreal_commands import (
    submit_command,
    get_command_status,
    wait_for_command,
    execute_command_sync,
    CommandStatus,
    CommandResult,
)

# Base Classes
from surreal_commands import CommandInput, CommandOutput

# Retry Configuration
from surreal_commands import RetryConfig, RetryStrategy
```

## Patterns

- **Decorator-based Registration**: Use `@command("name")` to register functions
- **Auto-detection**: App name derived from module package if not specified
- **Pydantic Validation**: All command inputs validated against Pydantic schemas
- **Sync/Async Duality**: All client functions have sync and async variants

## Gotchas

- **Import Order**: Commands must be imported before worker starts - worker only knows registered commands
- **Forward Reference**: `CommandRegistryItem.model_rebuild()` called at module load to resolve `RetryConfig`
- **Singleton**: `registry` is a singleton - all decorators register to the same instance
- **No Default Retry**: Retry disabled by default - enable via decorator or env vars

## When Adding Code

- Export new public symbols in `__init__.py` and add to `__all__`
- Command functions should accept Pydantic models and return Pydantic models
- Use `CommandInput` base for context access, `CommandOutput` base for auto-metadata
