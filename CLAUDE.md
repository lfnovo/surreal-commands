# Surreal Commands

Distributed task queue using SurrealDB and LangChain Runnables. Commands registered via decorators, queued in SurrealDB, executed by workers via LIVE queries.

## Structure

```
src/surreal_commands/
├── __init__.py       # Public API re-exports
├── decorators.py     # @command decorator
├── core/             # Execution engine
├── cli/              # CLI tools
└── repository/       # Database layer
```

## Modules

- **[core/](src/surreal_commands/core/CLAUDE.md)**: Registry, executor, service, worker, client, retry logic
- **[cli/](src/surreal_commands/cli/CLAUDE.md)**: Worker CLI, dashboard, logs viewer
- **[repository/](src/surreal_commands/repository/CLAUDE.md)**: SurrealDB connection and CRUD utilities

## Package-Level Files

- **`__init__.py`**: Re-exports public API (`command`, `registry`, `submit_command`, `wait_for_command`, `CommandInput`, `CommandOutput`, `RetryConfig`)
- **`decorators.py`**: `@command(name, app, retry)` decorator - wraps functions in `RunnableLambda`, registers to global `registry`

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SURREAL_URL` | WebSocket URL (`ws://host:port/rpc`) |
| `SURREAL_USER` | Database username |
| `SURREAL_PASSWORD` | Database password |
| `SURREAL_NAMESPACE` | SurrealDB namespace |
| `SURREAL_DATABASE` | SurrealDB database |
| `SURREAL_COMMANDS_MODULES` | Comma-separated modules for worker to import |
| `SURREAL_COMMANDS_RETRY_ENABLED` | Enable global retry |
| `SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS` | Max retry attempts |
| `SURREAL_COMMANDS_RETRY_WAIT_STRATEGY` | `fixed`, `exponential`, `random`, `exponential_jitter` |

## Gotchas

- **Import before worker**: Commands must be imported before worker starts - use `--import-modules` or `SURREAL_COMMANDS_MODULES`
- **Singleton registry**: All `@command` decorators register to global `registry` singleton
- **WebSocket URL**: SurrealDB uses `ws://` not `http://`
- **No in-memory fallback**: Real SurrealDB instance required

## Key Dependencies

- **langchain-core**: Commands wrapped as `RunnableLambda`
- **surrealdb**: Database client with LIVE query support
- **pydantic**: Input/output validation
- **tenacity**: Retry logic
- **typer**: CLI framework
