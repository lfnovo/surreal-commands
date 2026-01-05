# CLI

Command-line interface tools for the surreal-commands worker and utilities.

## Files

- **`__init__.py`**: Empty module marker
- **`launcher.py`**: Dynamic CLI generator - creates Typer commands from registered commands
- **`worker.py`**: Worker CLI entry point - re-exports `core/worker.py` app
- **`dashboard.py`**: Live dashboard showing command status (Rich table + SurrealDB LIVE query)
- **`logs.py`**: Live event stream viewer (Rich console + SurrealDB LIVE subscription)

## Patterns

- **Dynamic Command Generation**: `launcher.py` uses `exec()` to generate Typer commands from Pydantic schemas
- **Entry Points**: Each CLI tool has a `main()` function for pyproject.toml script entry points
- **Rich Output**: All CLIs use Rich for formatted terminal output

## Integration

- Imports from: `core/registry`, `core/service`, `core/worker`, `repository`
- Entry points: `surreal-commands-worker` (worker.py), `surreal-commands-dashboard` (dashboard.py), `surreal-commands-logs` (logs.py)

## Gotchas

- `launcher.py` uses `exec()` for dynamic function creation - type annotations converted to strings for Typer compatibility
- Complex types (custom classes, datetime) are converted to `str` type in CLI
- `dashboard.py` and `logs.py` use Click instead of Typer (inconsistent with worker.py)
- Worker entry point delegates to `core/worker.py` - actual worker logic is there, not here

## When Adding Code

- Use Typer for new CLI tools to match worker pattern
- Complex Pydantic types become string arguments - document JSON format if needed
- Add entry point to pyproject.toml `[project.scripts]` section
