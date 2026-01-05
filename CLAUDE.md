# Surreal Commands

Distributed task queue library using SurrealDB and LangChain Runnables. Similar to Celery but with real-time command processing via SurrealDB LIVE queries.

## Directory Structure

```
surreal-commands/
├── src/surreal_commands/    # Main package
│   ├── core/                # Execution engine
│   ├── cli/                 # CLI tools
│   └── repository/          # Database layer
├── tests/                   # Pytest test suite
└── examples/                # Usage examples
```

See [src/surreal_commands/CLAUDE.md](src/surreal_commands/CLAUDE.md) for package details.

## Development

- **Python**: 3.10.6+
- **Package Manager**: uv
- **Testing**: `uv run pytest`
- **Linting**: `uv run ruff check .`
- **Type Check**: `uv run mypy src/`

## Key Dependencies

- **langchain-core**: Command wrapping as Runnables
- **surrealdb**: Database and real-time queue
- **pydantic**: Input/output validation
- **tenacity**: Retry logic
- **typer/rich**: CLI interface

## Environment Variables

```bash
# SurrealDB (required)
SURREAL_URL=ws://localhost:8000/rpc
SURREAL_USER=root
SURREAL_PASSWORD=root
SURREAL_NAMESPACE=test
SURREAL_DATABASE=test

# Retry (optional)
SURREAL_COMMANDS_RETRY_ENABLED=false
SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS=3
SURREAL_COMMANDS_RETRY_WAIT_STRATEGY=exponential

# Worker (optional)
SURREAL_COMMANDS_MODULES=my_tasks,my_commands
```

## CLI Commands

```bash
# Start worker
surreal-commands-worker --import-modules "my_tasks" --max-tasks 5

# Dashboard (basic)
surreal-commands-dashboard

# Live logs
surreal-commands-logs
```

## Testing

- Uses pytest with pytest-asyncio
- Fixtures in `tests/conftest.py`: `clean_registry`, `mock_db`, `sample_command_function`
- Run: `uv run pytest tests/ -v`

## Gotchas

- **Import before worker**: Commands must be imported before worker starts via `--import-modules` or `SURREAL_COMMANDS_MODULES`
- **Singleton registry**: All `@command` decorators register to global `registry` singleton
- **SurrealDB required**: Real database needed for integration - no in-memory fallback
- **WebSocket URL**: SurrealDB uses `ws://` not `http://` for connection
