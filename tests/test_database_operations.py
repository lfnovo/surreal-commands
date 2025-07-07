"""Tests for database operations and repository functionality"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from surrealdb import RecordID

from src.surreal_commands.repository import (
    db_connection,
    ensure_record_id,
    parse_record_id,
    parse_record_ids,
    repo_create,
    repo_query,
    repo_relate,
    repo_update,
    repo_upsert,
    sync_db_connection,
)


@pytest.fixture
def mock_async_surreal():
    """Mock AsyncSurreal database connection"""
    mock_db = AsyncMock()
    mock_db.signin = AsyncMock()
    mock_db.use = AsyncMock()
    mock_db.query = AsyncMock()
    mock_db.create = AsyncMock()
    mock_db.merge = AsyncMock()
    mock_db.close = AsyncMock()
    return mock_db


@pytest.fixture
def mock_sync_surreal():
    """Mock Surreal database connection"""
    mock_db = Mock()
    mock_db.signin = Mock()
    mock_db.use = Mock()
    mock_db.query = Mock()
    mock_db.create = Mock()
    mock_db.merge = Mock()
    return mock_db


@pytest.fixture
def sample_record():
    """Sample database record for testing"""
    return {
        "id": "command:test123",
        "app": "test_app",
        "name": "test_command",
        "args": {"text": "hello"},
        "status": "new",
        "created": "2024-01-01T00:00:00Z",
        "updated": "2024-01-01T00:00:00Z",
    }


@pytest.mark.unit
class TestRecordUtilities:
    """Test utility functions for record handling"""

    def test_parse_record_ids_with_dict(self):
        """Test parsing RecordIDs in a dictionary"""
        record_id = RecordID("command", "test123")
        data = {"id": record_id, "name": "test", "nested": {"record_id": record_id}}

        parsed = parse_record_ids(data)

        assert parsed["id"] == "command:test123"
        assert parsed["name"] == "test"
        assert parsed["nested"]["record_id"] == "command:test123"

    def test_parse_record_ids_with_list(self):
        """Test parsing RecordIDs in a list"""
        record_id = RecordID("command", "test123")
        data = [
            {"id": record_id, "name": "test1"},
            {"id": RecordID("command", "test456"), "name": "test2"},
        ]

        parsed = parse_record_ids(data)

        assert len(parsed) == 2
        assert parsed[0]["id"] == "command:test123"
        assert parsed[1]["id"] == "command:test456"

    def test_parse_record_ids_with_primitive_types(self):
        """Test that primitive types are unchanged"""
        assert parse_record_ids("string") == "string"
        assert parse_record_ids(123) == 123
        assert parse_record_ids(True) is True

    def test_ensure_record_id_from_string(self):
        """Test converting string to RecordID"""
        result = ensure_record_id("command:test123")
        assert isinstance(result, RecordID)
        assert str(result) == "command:test123"

    def test_ensure_record_id_from_record_id(self):
        """Test that RecordID is returned unchanged"""
        record_id = RecordID("command", "test123")
        result = ensure_record_id(record_id)
        assert result is record_id

    def test_parse_record_id_functionality(self):
        """Test parse_record_id function"""
        # Test with string
        result1 = parse_record_id("command:test123")
        assert isinstance(result1, RecordID)

        # Test with existing RecordID
        record_id = RecordID("command", "test123")
        result2 = parse_record_id(record_id)
        assert result2 is record_id


@pytest.mark.unit
class TestDatabaseConnections:
    """Test database connection context managers"""

    @pytest.mark.asyncio
    async def test_db_connection_with_defaults(self, mock_async_surreal):
        """Test async database connection with environment defaults"""
        with patch(
            "src.surreal_commands.repository.AsyncSurreal"
        ) as mock_surreal_class:
            mock_db = mock_async_surreal
            mock_surreal_class.return_value = mock_db

            with patch.dict(
                "os.environ",
                {
                    "SURREAL_USER": "test_user",
                    "SURREAL_PASSWORD": "test_pass",
                    "SURREAL_NAMESPACE": "test_ns",
                    "SURREAL_DATABASE": "test_db",
                },
            ):
                async with db_connection() as db:
                    assert db is mock_db

                # Verify connection setup
                mock_db.signin.assert_called_once_with(
                    {"username": "test_user", "password": "test_pass"}
                )
                mock_db.use.assert_called_once_with("test_ns", "test_db")
                mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_connection_with_custom_params(self, mock_async_surreal):
        """Test async database connection with custom parameters"""
        with patch(
            "src.surreal_commands.repository.AsyncSurreal"
        ) as mock_surreal_class:
            mock_db = mock_async_surreal
            mock_surreal_class.return_value = mock_db

            async with db_connection(
                url="custom_url",
                user="custom_user",
                password="custom_pass",
                namespace="custom_ns",
                database="custom_db",
            ) as db:
                assert db is mock_db

            # Verify custom parameters were used
            mock_surreal_class.assert_called_once_with("custom_url")
            mock_db.signin.assert_called_once_with(
                {"username": "custom_user", "password": "custom_pass"}
            )
            mock_db.use.assert_called_once_with("custom_ns", "custom_db")

    def test_sync_db_connection(self, mock_sync_surreal):
        """Test synchronous database connection"""
        with patch("src.surreal_commands.repository.Surreal") as mock_surreal_class:
            mock_db = mock_sync_surreal
            mock_surreal_class.return_value = mock_db

            with patch.dict(
                "os.environ",
                {
                    "SURREAL_USER": "test_user",
                    "SURREAL_PASSWORD": "test_pass",
                    "SURREAL_NAMESPACE": "test_ns",
                    "SURREAL_DATABASE": "test_db",
                },
            ):
                with sync_db_connection() as db:
                    assert db is mock_db

                # Verify connection setup
                mock_db.signin.assert_called_once_with(
                    {"username": "test_user", "password": "test_pass"}
                )
                mock_db.use.assert_called_once_with("test_ns", "test_db")


@pytest.mark.unit
class TestRepositoryOperations:
    """Test repository CRUD operations"""

    @pytest.mark.asyncio
    async def test_repo_query_success(self, mock_async_surreal):
        """Test successful query execution"""
        mock_result = [{"id": "command:test123", "name": "test"}]

        with patch("src.surreal_commands.repository.db_connection") as mock_conn:
            mock_db = mock_async_surreal
            mock_db.query.return_value = mock_result
            mock_conn.return_value.__aenter__.return_value = mock_db

            result = await repo_query("SELECT * FROM command")

            assert result == mock_result
            mock_db.query.assert_called_once_with("SELECT * FROM command", None)

    @pytest.mark.asyncio
    async def test_repo_query_with_variables(self, mock_async_surreal):
        """Test query execution with variables"""
        mock_result = [{"id": "command:test123"}]
        variables = {"status": "new"}

        with patch("src.surreal_commands.repository.db_connection") as mock_conn:
            mock_db = mock_async_surreal
            mock_db.query.return_value = mock_result
            mock_conn.return_value.__aenter__.return_value = mock_db

            result = await repo_query(
                "SELECT * FROM command WHERE status = $status", variables
            )

            assert result == mock_result
            mock_db.query.assert_called_once_with(
                "SELECT * FROM command WHERE status = $status", variables
            )

    @pytest.mark.asyncio
    async def test_repo_query_error_handling(self, mock_async_surreal):
        """Test query error handling"""
        with patch("src.surreal_commands.repository.db_connection") as mock_conn:
            mock_db = mock_async_surreal
            mock_db.query.side_effect = Exception("Database error")
            mock_conn.return_value.__aenter__.return_value = mock_db

            with pytest.raises(Exception, match="Database error"):
                await repo_query("INVALID QUERY")

    @pytest.mark.asyncio
    async def test_repo_create_success(self, mock_async_surreal):
        """Test successful record creation"""
        data = {"name": "test_command", "status": "new"}
        mock_result = {"id": "command:test123", **data}

        with patch("src.surreal_commands.repository.db_connection") as mock_conn:
            mock_db = mock_async_surreal
            mock_db.create.return_value = mock_result
            mock_conn.return_value.__aenter__.return_value = mock_db

            result = await repo_create("command", data)

            assert result == mock_result

            # Verify that created and updated timestamps were added
            call_args = mock_db.create.call_args[0]
            assert call_args[0] == "command"
            created_data = call_args[1]
            assert "created" in created_data
            assert "updated" in created_data
            assert created_data["name"] == "test_command"

    @pytest.mark.asyncio
    async def test_repo_create_removes_id(self, mock_async_surreal):
        """Test that create operation removes id from data"""
        data = {"id": "should_be_removed", "name": "test"}

        with patch("src.surreal_commands.repository.db_connection") as mock_conn:
            mock_db = mock_async_surreal
            mock_db.create.return_value = {"id": "command:new123"}
            mock_conn.return_value.__aenter__.return_value = mock_db

            await repo_create("command", data)

            # Verify id was removed from the data passed to create
            call_args = mock_db.create.call_args[0][1]
            assert "id" not in call_args
            assert call_args["name"] == "test"

    @pytest.mark.asyncio
    async def test_repo_upsert_with_id(self):
        """Test upsert operation with specific ID"""
        data = {"status": "updated"}
        record_id = "command:test123"

        with patch("src.surreal_commands.repository.repo_query") as mock_query:
            mock_query.return_value = [{"id": record_id, **data}]

            result = await repo_upsert("command", record_id, data)

            assert len(result) == 1
            mock_query.assert_called_once()

            # Verify the query was constructed correctly
            query_call = mock_query.call_args[0][0]
            assert "UPSERT command:test123 MERGE $data" in query_call

    @pytest.mark.asyncio
    async def test_repo_upsert_without_id(self):
        """Test upsert operation without specific ID"""
        data = {"name": "test"}

        with patch("src.surreal_commands.repository.repo_query") as mock_query:
            mock_query.return_value = [{"id": "command:generated123", **data}]

            result = await repo_upsert("command", None, data)

            assert len(result) == 1
            mock_query.assert_called_once()

            # Verify the query was constructed correctly (should use table name)
            query_call = mock_query.call_args[0][0]
            assert "UPSERT command MERGE $data" in query_call

    @pytest.mark.asyncio
    async def test_repo_update_success(self):
        """Test successful record update"""
        data = {"status": "completed"}
        record_id = "test123"

        with patch("src.surreal_commands.repository.repo_query") as mock_query:
            mock_query.return_value = {"id": f"command:{record_id}", **data}

            result = await repo_update("command", record_id, data)

            assert len(result) == 1
            mock_query.assert_called_once()

            # Verify update query construction
            query_call = mock_query.call_args[0][0]
            assert "UPDATE command:test123 MERGE $data" in query_call

    @pytest.mark.asyncio
    async def test_repo_update_with_full_record_id(self):
        """Test update with full record ID"""
        data = {"status": "completed"}
        record_id = "command:test123"

        with patch("src.surreal_commands.repository.repo_query") as mock_query:
            mock_query.return_value = {"id": record_id, **data}

            result = await repo_update("command", record_id, data)

            assert len(result) == 1

            # Should use the record ID as-is
            query_call = mock_query.call_args[0][0]
            assert "UPDATE command:test123 MERGE $data" in query_call

    @pytest.mark.asyncio
    async def test_repo_relate_success(self):
        """Test creating relationships between records"""
        source = "user:john"
        relationship = "owns"
        target = "document:doc123"
        data = {"since": "2024-01-01"}

        with patch("src.surreal_commands.repository.repo_query") as mock_query:
            mock_query.return_value = [{"id": "owns:relation123", **data}]

            result = await repo_relate(source, relationship, target, data)

            assert len(result) == 1
            mock_query.assert_called_once()

            # Verify relationship query construction
            query_call = mock_query.call_args[0][0]
            assert "RELATE user:john->owns->document:doc123 CONTENT $data" in query_call

    @pytest.mark.asyncio
    async def test_repo_relate_without_data(self):
        """Test creating relationships without additional data"""
        source = "user:john"
        relationship = "follows"
        target = "user:jane"

        with patch("src.surreal_commands.repository.repo_query") as mock_query:
            mock_query.return_value = [{"id": "follows:relation123"}]

            result = await repo_relate(source, relationship, target)

            assert len(result) == 1

            # Verify empty data dict was passed
            query_vars = mock_query.call_args[0][1]
            assert query_vars["data"] == {}


@pytest.mark.integration
@pytest.mark.requires_db
class TestDatabaseIntegration:
    """Integration tests that require actual database connection"""

    @pytest.mark.asyncio
    async def test_full_crud_cycle(self):
        """Test complete CRUD cycle (requires actual SurrealDB)"""
        # This test would require a real SurrealDB instance
        # and would be marked with @pytest.mark.requires_db
        # so it can be skipped in environments without DB
        pytest.skip("Requires actual SurrealDB connection")

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test handling of connection errors"""
        # Test what happens when database is unavailable
        pytest.skip("Requires controlled database environment")
