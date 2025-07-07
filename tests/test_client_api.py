"""Tests for client API functionality"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from surrealdb import RecordID

from src.surreal_commands.core.client import (
    submit_command,
    get_command_status,
    get_command_status_sync,
    wait_for_command,
    wait_for_command_sync,
    execute_command_sync,
    CommandStatus,
    CommandResult
)
from src.surreal_commands.core.service import CommandRequest


@pytest.fixture
def mock_command_service():
    """Mock command service for testing"""
    mock_service = Mock()
    mock_service.submit_command_sync = Mock()
    mock_service.submit_command = AsyncMock()
    return mock_service


@pytest.fixture
def sample_command_record():
    """Sample command record from database"""
    return {
        "id": "command:test123",
        "app": "test_app",
        "name": "test_command",
        "args": {"text": "hello"},
        "context": {},
        "status": "completed",
        "result": {"output": "processed hello"},
        "error_message": None,
        "created": "2024-01-01T00:00:00Z",
        "updated": "2024-01-01T00:00:05Z"
    }


@pytest.mark.unit
class TestCommandStatus:
    """Test CommandStatus enum"""
    
    def test_command_status_values(self):
        """Test that CommandStatus has expected values"""
        assert CommandStatus.NEW == "new"
        assert CommandStatus.RUNNING == "running"
        assert CommandStatus.COMPLETED == "completed"
        assert CommandStatus.FAILED == "failed"
        assert CommandStatus.CANCELED == "canceled"


@pytest.mark.unit
class TestCommandResult:
    """Test CommandResult class"""
    
    def test_command_result_initialization(self):
        """Test CommandResult initialization"""
        result = CommandResult(
            command_id="command:test123",
            status=CommandStatus.COMPLETED,
            result={"output": "test"},
            error_message=None,
            created="2024-01-01T00:00:00Z",
            updated="2024-01-01T00:00:05Z"
        )
        
        assert str(result.command_id) == "command:test123"
        assert result.status == CommandStatus.COMPLETED
        assert result.result == {"output": "test"}
        assert result.error_message is None
        assert result.created == "2024-01-01T00:00:00Z"
        assert result.updated == "2024-01-01T00:00:05Z"
    
    def test_command_result_is_complete_success(self):
        """Test is_complete for successful command"""
        result = CommandResult("command:test", CommandStatus.COMPLETED)
        assert result.is_complete() is True
        assert result.is_success() is True
    
    def test_command_result_is_complete_failed(self):
        """Test is_complete for failed command"""
        result = CommandResult("command:test", CommandStatus.FAILED)
        assert result.is_complete() is True
        assert result.is_success() is False
    
    def test_command_result_is_complete_canceled(self):
        """Test is_complete for canceled command"""
        result = CommandResult("command:test", CommandStatus.CANCELED)
        assert result.is_complete() is True
        assert result.is_success() is False
    
    def test_command_result_not_complete(self):
        """Test is_complete for running command"""
        result = CommandResult("command:test", CommandStatus.RUNNING)
        assert result.is_complete() is False
        assert result.is_success() is False
    
    def test_command_result_with_record_id(self):
        """Test CommandResult with RecordID"""
        record_id = RecordID("command", "test123")
        result = CommandResult(record_id, CommandStatus.COMPLETED)
        
        assert isinstance(result.command_id, RecordID)
        assert str(result.command_id) == "command:test123"


@pytest.mark.unit
class TestSubmitCommand:
    """Test command submission functionality"""
    
    def test_submit_command_success(self):
        """Test successful command submission"""
        with patch('src.surreal_commands.core.client.command_service') as mock_service:
            mock_service.submit_command_sync.return_value = "command:test123"
            
            result = submit_command(
                app="test_app",
                command="test_command",
                args={"text": "hello"},
                context={"user": "test"}
            )
            
            assert result == "command:test123"
            
            # Verify the service was called with correct parameters
            mock_service.submit_command_sync.assert_called_once()
            call_args = mock_service.submit_command_sync.call_args[0][0]
            assert isinstance(call_args, CommandRequest)
            assert call_args.app == "test_app"
            assert call_args.command == "test_command"
            assert call_args.args == {"text": "hello"}
            assert call_args.context == {"user": "test"}
    
    def test_submit_command_without_context(self):
        """Test command submission without context"""
        with patch('src.surreal_commands.core.client.command_service') as mock_service:
            mock_service.submit_command_sync.return_value = "command:test123"
            
            result = submit_command(
                app="test_app",
                command="test_command",
                args={"text": "hello"}
            )
            
            assert result == "command:test123"
            
            # Verify context defaults to None
            call_args = mock_service.submit_command_sync.call_args[0][0]
            assert call_args.context is None
    
    def test_submit_command_service_error(self):
        """Test command submission when service raises error"""
        with patch('src.surreal_commands.core.client.command_service') as mock_service:
            mock_service.submit_command_sync.side_effect = ValueError("Invalid command")
            
            with pytest.raises(ValueError, match="Invalid command"):
                submit_command("test_app", "test_command", {})


@pytest.mark.unit
class TestGetCommandStatus:
    """Test command status retrieval"""
    
    @pytest.mark.asyncio
    async def test_get_command_status_success(self, sample_command_record):
        """Test successful status retrieval"""
        with patch('src.surreal_commands.repository.repo_query') as mock_query:
            mock_query.return_value = [sample_command_record]
            
            result = await get_command_status("command:test123")
            
            assert isinstance(result, CommandResult)
            assert str(result.command_id) == "command:test123"
            assert result.status == CommandStatus.COMPLETED
            assert result.result == {"output": "processed hello"}
            assert result.error_message is None
            
            # Verify query was called correctly
            mock_query.assert_called_once_with(
                "SELECT * FROM $command_id",
                {"command_id": RecordID.parse("command:test123")}
            )
    
    @pytest.mark.asyncio
    async def test_get_command_status_not_found(self):
        """Test status retrieval for non-existent command"""
        with patch('src.surreal_commands.repository.repo_query') as mock_query:
            mock_query.return_value = []
            
            with pytest.raises(ValueError, match="Command command:test123 not found"):
                await get_command_status("command:test123")
    
    def test_get_command_status_sync(self, sample_command_record):
        """Test synchronous status retrieval"""
        with patch('src.surreal_commands.repository.repo_query') as mock_query:
            mock_query.return_value = [sample_command_record]
            
            # Mock asyncio.run to avoid actual async execution in test
            with patch('asyncio.run') as mock_run:
                mock_run.return_value = CommandResult(
                    "command:test123", 
                    CommandStatus.COMPLETED,
                    {"output": "processed hello"}
                )
                
                result = get_command_status_sync("command:test123")
                
                assert isinstance(result, CommandResult)
                assert str(result.command_id) == "command:test123"
                assert result.status == CommandStatus.COMPLETED


@pytest.mark.unit
class TestWaitForCommand:
    """Test waiting for command completion"""
    
    @pytest.mark.asyncio
    async def test_wait_for_command_immediate_completion(self, sample_command_record):
        """Test waiting for command that's already complete"""
        with patch('src.surreal_commands.core.client.get_command_status') as mock_status:
            result = CommandResult(
                "command:test123",
                CommandStatus.COMPLETED,
                {"output": "processed hello"}
            )
            mock_status.return_value = result
            
            final_result = await wait_for_command("command:test123")
            
            assert final_result is result
            assert final_result.is_complete()
            mock_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wait_for_command_with_polling(self, sample_command_record):
        """Test waiting for command that completes after polling"""
        with patch('src.surreal_commands.core.client.get_command_status') as mock_status:
            # First call returns running, second call returns completed
            running_result = CommandResult("command:test123", CommandStatus.RUNNING)
            completed_result = CommandResult(
                "command:test123", 
                CommandStatus.COMPLETED,
                {"output": "processed hello"}
            )
            mock_status.side_effect = [running_result, completed_result]
            
            with patch('asyncio.sleep') as mock_sleep:
                final_result = await wait_for_command("command:test123", poll_interval=0.1)
                
                assert final_result is completed_result
                assert final_result.is_complete()
                assert mock_status.call_count == 2
                mock_sleep.assert_called_once_with(0.1)
    
    @pytest.mark.asyncio
    async def test_wait_for_command_timeout(self):
        """Test timeout when waiting for command"""
        with patch('src.surreal_commands.core.client.get_command_status') as mock_status:
            # Always return running status
            running_result = CommandResult("command:test123", CommandStatus.RUNNING)
            mock_status.return_value = running_result
            
            with patch('asyncio.sleep'):
                with pytest.raises(TimeoutError, match="did not complete within 0.1 seconds"):
                    await wait_for_command("command:test123", timeout=0.1, poll_interval=0.05)
    
    def test_wait_for_command_sync(self):
        """Test synchronous wait for command"""
        completed_result = CommandResult(
            "command:test123", 
            CommandStatus.COMPLETED,
            {"output": "processed hello"}
        )
        
        with patch('asyncio.run') as mock_run:
            mock_run.return_value = completed_result
            
            result = wait_for_command_sync("command:test123", timeout=30)
            
            assert result is completed_result
            mock_run.assert_called_once()


@pytest.mark.unit
class TestExecuteCommandSync:
    """Test synchronous command execution"""
    
    def test_execute_command_sync_success(self):
        """Test successful synchronous command execution"""
        with patch('src.surreal_commands.core.client.submit_command') as mock_submit:
            with patch('src.surreal_commands.core.client.wait_for_command_sync') as mock_wait:
                mock_submit.return_value = "command:test123"
                mock_result = CommandResult(
                    "command:test123",
                    CommandStatus.COMPLETED,
                    {"output": "processed hello"}
                )
                mock_wait.return_value = mock_result
                
                result = execute_command_sync(
                    app="test_app",
                    command="test_command",
                    args={"text": "hello"},
                    context={"user": "test"},
                    timeout=30
                )
                
                assert result is mock_result
                
                # Verify submit was called correctly
                mock_submit.assert_called_once_with(
                    "test_app", "test_command", {"text": "hello"}, {"user": "test"}
                )
                
                # Verify wait was called correctly
                mock_wait.assert_called_once_with("command:test123", 30)
    
    def test_execute_command_sync_without_context_and_timeout(self):
        """Test execution without optional parameters"""
        with patch('src.surreal_commands.core.client.submit_command') as mock_submit:
            with patch('src.surreal_commands.core.client.wait_for_command_sync') as mock_wait:
                mock_submit.return_value = "command:test123"
                mock_result = CommandResult("command:test123", CommandStatus.COMPLETED)
                mock_wait.return_value = mock_result
                
                result = execute_command_sync(
                    app="test_app",
                    command="test_command",
                    args={"text": "hello"}
                )
                
                assert result is mock_result
                
                # Verify default values were used
                mock_submit.assert_called_once_with(
                    "test_app", "test_command", {"text": "hello"}, None
                )
                mock_wait.assert_called_once_with("command:test123", None)
    
    def test_execute_command_sync_submission_failure(self):
        """Test handling of submission failure"""
        with patch('src.surreal_commands.core.client.submit_command') as mock_submit:
            mock_submit.side_effect = ValueError("Submission failed")
            
            with pytest.raises(ValueError, match="Submission failed"):
                execute_command_sync("test_app", "test_command", {})
    
    def test_execute_command_sync_wait_timeout(self):
        """Test handling of wait timeout"""
        with patch('src.surreal_commands.core.client.submit_command') as mock_submit:
            with patch('src.surreal_commands.core.client.wait_for_command_sync') as mock_wait:
                mock_submit.return_value = "command:test123"
                mock_wait.side_effect = TimeoutError("Command timeout")
                
                with pytest.raises(TimeoutError, match="Command timeout"):
                    execute_command_sync("test_app", "test_command", {}, timeout=1)


@pytest.mark.integration
class TestClientAPIIntegration:
    """Integration tests for client API"""
    
    @pytest.mark.asyncio
    async def test_full_command_lifecycle(self):
        """Test complete command lifecycle from submission to completion"""
        # This would test the full integration with actual services
        # Marked as integration test to be run separately
        pytest.skip("Requires full service integration")
    
    def test_error_propagation(self):
        """Test that errors are properly propagated through the API"""
        # Test various error scenarios in the client API
        pytest.skip("Requires controlled error injection")


@pytest.mark.unit
class TestRecordIdHandling:
    """Test RecordID handling in client API"""
    
    @pytest.mark.asyncio
    async def test_get_status_with_string_id(self, sample_command_record):
        """Test status retrieval with string command ID"""
        with patch('src.surreal_commands.repository.repo_query') as mock_query:
            mock_query.return_value = [sample_command_record]
            
            result = await get_command_status("command:test123")
            
            # Verify that string was converted to RecordID for query
            query_vars = mock_query.call_args[0][1]
            assert isinstance(query_vars["command_id"], RecordID)
            assert str(query_vars["command_id"]) == "command:test123"
    
    @pytest.mark.asyncio
    async def test_get_status_with_record_id(self, sample_command_record):
        """Test status retrieval with RecordID command ID"""
        record_id = RecordID("command", "test123")
        
        with patch('src.surreal_commands.repository.repo_query') as mock_query:
            mock_query.return_value = [sample_command_record]
            
            result = await get_command_status(record_id)
            
            # Verify that RecordID was passed through correctly
            query_vars = mock_query.call_args[0][1]
            assert query_vars["command_id"] is record_id