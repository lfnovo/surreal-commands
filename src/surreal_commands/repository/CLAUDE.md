# Repository

SurrealDB database connection and query utilities for the command queue.

## Files

- **`__init__.py`**: Database connection context managers (async/sync), CRUD operations, RecordID utilities

## Patterns

- **Context Managers**: Use `db_connection()` (async) or `sync_db_connection()` (sync) as context managers
- **RecordID Handling**: All functions automatically convert RecordID objects to strings via `parse_record_ids()`
- **Timestamps**: `repo_create` and `repo_update` auto-add `created`/`updated` timestamps

## Integration

- Imports from: `surrealdb` (AsyncSurreal, Surreal, RecordID)
- Used by: `core/service.py`, `core/client.py`, `core/worker.py`, `cli/dashboard.py`, `cli/logs.py`
- Config: Reads `SURREAL_URL`, `SURREAL_USER`, `SURREAL_PASSWORD`, `SURREAL_NAMESPACE`, `SURREAL_DATABASE` from env

## Gotchas

- `sync_db_connection()` requires env vars to be set (no defaults for auth), while async version has defaults
- `repo_create()` strips `id` from data dict before insert - SurrealDB auto-generates IDs
- All query results go through `parse_record_ids()` - RecordIDs become strings in returned data
- `db_connection()` uses WebSocket URL format: `ws://host:port/rpc`

## When Adding Code

- Always use context managers for connections - never create bare Surreal instances
- Use `ensure_record_id()` to normalize string/RecordID inputs
- Return parsed results via `parse_record_ids()` for consistent string IDs
