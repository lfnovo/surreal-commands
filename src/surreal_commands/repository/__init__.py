import os
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar, Union

from loguru import logger
from surrealdb import AsyncSurreal, RecordID, Surreal  # type: ignore

T = TypeVar("T", Dict[str, Any], List[Dict[str, Any]])


def parse_record_ids(obj: Any) -> Any:
    """Recursively parse and convert RecordIDs into strings."""
    if isinstance(obj, dict):
        return {k: parse_record_ids(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_record_ids(item) for item in obj]
    elif isinstance(obj, RecordID):
        return str(obj)
    return obj


def ensure_record_id(value: Union[str, RecordID]) -> RecordID:
    """Ensure a value is a RecordID."""
    if isinstance(value, RecordID):
        return value
    return RecordID.parse(value)


def parse_record_id(value):
    """Parse a value into a RecordID."""
    if isinstance(value, RecordID):
        return value
    return RecordID.parse(value)


@asynccontextmanager
async def db_connection(
    url=None, user=None, password=None, namespace=None, database=None
):
    surreal_url = (
        url
        or os.environ.get("SURREAL_URL")
        or f"ws://{os.environ.get('SURREAL_ADDRESS', 'localhost')}:{os.environ.get('SURREAL_PORT', 8000)}/rpc"
    )
    db = AsyncSurreal(surreal_url)
    await db.signin(
        {
            "username": user or os.environ.get("SURREAL_USER", "test"),
            "password": password
            or os.environ.get("SURREAL_PASSWORD")
            or os.environ.get("SURREAL_PASS", "test"),
        }
    )
    await db.use(
        namespace or os.environ.get("SURREAL_NAMESPACE", "test"),
        database or os.environ.get("SURREAL_DATABASE", "test"),
    )
    try:
        yield db
    finally:
        await db.close()


@contextmanager
def sync_db_connection(
    url=None, user=None, password=None, namespace=None, database=None
):
    surreal_url = (
        url
        or os.environ.get("SURREAL_URL")
        or f"ws://{os.environ.get('SURREAL_ADDRESS', 'localhost')}:{os.environ.get('SURREAL_PORT', 8000)}/rpc"
    )
    db = Surreal(surreal_url)
    db.signin(
        {
            "username": user or os.environ["SURREAL_USER"],
            "password": password or os.environ["SURREAL_PASSWORD"],
        }
    )
    db.use(
        namespace or os.environ["SURREAL_NAMESPACE"],
        database or os.environ["SURREAL_DATABASE"],
    )
    yield db


async def repo_query(
    query_str: str, vars: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Execute a SurrealQL query and return the results"""

    async with db_connection() as connection:
        try:
            result = await connection.query(query_str, vars)
            if not isinstance(result, list) and not isinstance(result, dict):
                raise Exception(result)
            return parse_record_ids(result)
        except Exception as e:
            logger.error(f"Query: {query_str[:200]}")
            logger.exception(e)
            raise


async def repo_create(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new record in the specified table"""
    # Remove 'id' attribute if it exists in data
    data.pop("id", None)
    data["created"] = data.get("created", datetime.now(timezone.utc))
    data["updated"] = data.get("updated", datetime.now(timezone.utc))
    try:
        async with db_connection() as connection:
            return await connection.create(table, data)
    except Exception as e:
        logger.exception(e)
        raise RuntimeError("Failed to create record")


async def repo_relate(
    source: str, relationship: str, target: str, data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Create a relationship between two records with optional data"""
    if data is None:
        data = {}
    query = f"RELATE {source}->{relationship}->{target} CONTENT $data;"
    return await repo_query(
        query,
        {
            "data": data,
        },
    )


async def repo_upsert(
    table: str,
    id: Optional[Union[str, RecordID]],
    data: Dict[str, Any],
    add_timestamp=False,
) -> List[Dict[str, Any]]:
    """Create or update a record in the specified table"""
    data.pop("id", None)
    if isinstance(id, RecordID):
        id = str(id)
    if add_timestamp:
        data["updated"] = datetime.now(timezone.utc)
    query = f"UPSERT {id if id else table} MERGE $data;"
    return await repo_query(query, {"data": data})


async def repo_update(
    table: str, id: str, data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Update an existing record by table and id"""
    # If id already contains the table name, use it as is
    try:
        if isinstance(id, RecordID) or (":" in id and id.startswith(f"{table}:")):
            record_id = id
        else:
            record_id = f"{table}:{id}"
        data["updated"] = data.get("updated", datetime.now(timezone.utc))
        query = f"UPDATE {record_id} MERGE $data;"
        result = await repo_query(query, {"data": data})
        return [parse_record_ids(result)]
    except Exception as e:
        raise RuntimeError(f"Failed to update record: {str(e)}")


# def repo_delete(record_id: str) -> bool:
#     """Delete a record by record id"""
#     # If id already contains the table name, use it as is

#     query = f"DELETE ONLY {record_id} RETURN BEFORE;"
#     delete_result = repo_query(query)
#     # logger.debug(f"Delete query: {query}")
#     return len(delete_result) > 0


# def repo_select(table_name: str, order_by=None) -> List[Dict[str, Any]]:
#     try:
#         query = f"SELECT * omit embedding FROM {table_name}"
#         if order_by:
#             query += f" ORDER BY {order_by}"

#         results = repo_query(query)
#         return [_return_data(result) for result in results]
#     except Exception as e:
#         raise
#         # logger.exception(e)
#         # raise RuntimeError(f"Failed to fetch records: {str(e)}")


# def repo_get(record_id: str) -> Dict[str, Any]:
#     try:
#         results = repo_query(f"SELECT * omit embedding FROM {record_id}")
#         if not results:
#             raise KeyError(f"Record with record_id {record_id} not found")
#         return _return_data(results[0])
#     except Exception as e:
#         logger.exception(e)
#         raise RuntimeError(f"Failed to fetch record: {str(e)}")
