"""Tests for command execution functionality"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from pydantic import BaseModel
from langchain_core.runnables import RunnableLambda

from src.surreal_commands.core.executor import CommandExecutor


class TestInput(BaseModel):
    text: str
    count: int = 1


class TestOutput(BaseModel):
    result: str
    status: str = "completed"


class InvalidInput(BaseModel):
    invalid_field: str


@pytest.fixture
def sync_command():
    """Sync command function for testing"""
    def process_sync(input_data: TestInput) -> TestOutput:
        return TestOutput(result=f"sync: {input_data.text} x{input_data.count}")
    return RunnableLambda(process_sync)


@pytest.fixture
async def async_command():
    """Async command function for testing"""
    async def process_async(input_data: TestInput) -> TestOutput:
        await asyncio.sleep(0.01)  # Small delay to simulate async work
        return TestOutput(result=f"async: {input_data.text} x{input_data.count}")
    return RunnableLambda(process_async)


@pytest.fixture
def failing_command():
    """Command that raises an exception"""
    def failing_process(input_data: TestInput) -> TestOutput:
        raise ValueError("Command failed intentionally")
    return RunnableLambda(failing_process)


@pytest.fixture
def dict_input_command():
    """Command that accepts dict input"""
    def process_dict(input_data: dict) -> dict:
        return {"result": f"processed: {input_data.get('text', 'default')}"}
    return RunnableLambda(process_dict)


@pytest.fixture
def command_executor():
    """CommandExecutor instance for testing"""
    return CommandExecutor({})


@pytest.mark.unit
class TestCommandExecutor:
    """Test CommandExecutor functionality"""
    
    def test_init(self):
        """Test CommandExecutor initialization"""
        commands = {"app.command": Mock()}
        executor = CommandExecutor(commands)
        assert executor.command_dict == commands
    
    def test_parse_input_with_pydantic_model(self, sync_command):
        """Test parsing input with Pydantic models"""
        # Test with dict input
        input_dict = {"text": "hello", "count": 2}
        parsed = CommandExecutor.parse_input(sync_command, input_dict)
        
        assert isinstance(parsed, TestInput)
        assert parsed.text == "hello"
        assert parsed.count == 2
    
    def test_parse_input_with_existing_model(self, sync_command):
        """Test parsing input that's already the correct model"""
        input_model = TestInput(text="hello", count=2)
        parsed = CommandExecutor.parse_input(sync_command, input_model)
        
        assert parsed is input_model
    
    def test_parse_input_with_dict_command(self, dict_input_command):
        """Test parsing input for commands that expect dict"""
        input_dict = {"text": "hello"}
        parsed = CommandExecutor.parse_input(dict_input_command, input_dict)
        
        # LangChain may wrap dict inputs, check if data is accessible
        if hasattr(parsed, 'root'):
            assert parsed.root == input_dict
        elif hasattr(parsed, '__dict__') and 'text' in str(parsed):
            # LangChain wrapped object, check it contains the expected data
            assert 'hello' in str(parsed)
        else:
            assert parsed == input_dict
    
    def test_fix_return_type_with_pydantic(self, command_executor):
        """Test fixing return type with Pydantic models"""
        # Test with dict that should become Pydantic model
        return_class = TestOutput
        value = {"result": "test", "status": "done"}
        
        fixed = command_executor._fix_return_type(return_class, value)
        assert isinstance(fixed, TestOutput)
        assert fixed.result == "test"
        assert fixed.status == "done"
    
    def test_fix_return_type_with_existing_model(self, command_executor):
        """Test fixing return type with existing Pydantic model"""
        return_class = TestOutput
        value = TestOutput(result="test")
        
        fixed = command_executor._fix_return_type(return_class, value)
        assert fixed == value
    
    def test_fix_return_type_no_conversion_needed(self, command_executor):
        """Test that non-convertible types are returned as-is"""
        value = "simple string"
        fixed = command_executor._fix_return_type(str, value)
        assert fixed == value
    
    def test_classify_command_runnable(self, command_executor, sync_command):
        """Test classifying a Runnable command"""
        classification = command_executor.classify_command(sync_command)
        assert classification == "runnable"
    
    def test_classify_command_other(self, command_executor):
        """Test classifying a non-Runnable command"""
        classification = command_executor.classify_command("not a runnable")
        assert classification == "other"


@pytest.mark.unit
class TestSyncExecution:
    """Test synchronous command execution"""
    
    def test_execute_sync_basic(self):
        """Test basic synchronous execution"""
        sync_command = RunnableLambda(lambda x: TestOutput(result=f"sync: {x.text}"))
        executor = CommandExecutor({"test_command": sync_command})
        
        input_data = TestInput(text="hello")
        result = executor.execute_sync("test_command", input_data)
        
        # LangChain wraps results in RunnableLambdaOutput, check actual data
        assert hasattr(result, 'root') or hasattr(result, 'result')
        if hasattr(result, 'root'):
            assert result.root['result'] == "sync: hello"
        else:
            assert result.result == "sync: hello"
    
    def test_execute_sync_with_dict_input(self):
        """Test sync execution with dict input"""
        def sync_func(x):
            # Handle LangChain input wrapping
            text = getattr(x, 'text', None) or (x.root.get('text') if hasattr(x, 'root') else x.get('text'))
            return TestOutput(result=f"sync: {text}")
        
        sync_command = RunnableLambda(sync_func)
        executor = CommandExecutor({"test_command": sync_command})
        
        input_dict = {"text": "hello", "count": 1}
        result = executor.execute_sync("test_command", input_dict)
        
        # LangChain wraps results in RunnableLambdaOutput, check actual data
        assert hasattr(result, 'root') or hasattr(result, 'result')
        if hasattr(result, 'root'):
            assert result.root['result'] == "sync: hello"
        else:
            assert result.result == "sync: hello"
    
    def test_execute_sync_command_not_found(self):
        """Test sync execution with non-existent command"""
        executor = CommandExecutor({})
        
        with pytest.raises(KeyError):
            executor.execute_sync("nonexistent_command", {})
    
    def test_execute_sync_with_error(self):
        """Test sync execution with command that raises an error"""
        failing_command = RunnableLambda(lambda x: (_ for _ in ()).throw(ValueError("Test error")))
        executor = CommandExecutor({"failing_command": failing_command})
        
        with pytest.raises(ValueError, match="Test error"):
            executor.execute_sync("failing_command", TestInput(text="test"))
    
    def test_execute_sync_fallback_to_async(self):
        """Test sync execution falling back to async when sync is not available"""
        # Create a command that only supports async
        async def async_only(input_data):
            return TestOutput(result=f"async: {input_data.text}")
        
        async_command = RunnableLambda(async_only)
        # Mock the invoke method to raise TypeError (sync not supported)
        with patch.object(async_command, 'invoke', side_effect=TypeError("No synchronous function provided")):
            with patch.object(async_command, 'ainvoke', return_value=TestOutput(result="async: test")):
                executor = CommandExecutor({"async_command": async_command})
                
                result = executor.execute_sync("async_command", TestInput(text="test"))
                # LangChain wraps results, check actual data
                assert hasattr(result, 'root') or hasattr(result, 'result')


@pytest.mark.unit
class TestAsyncExecution:
    """Test asynchronous command execution"""
    
    @pytest.mark.asyncio
    async def test_execute_async_basic(self):
        """Test basic asynchronous execution"""
        async def async_func(input_data):
            return TestOutput(result=f"async: {input_data.text}")
        
        async_command = RunnableLambda(async_func)
        executor = CommandExecutor({"test_command": async_command})
        
        input_data = TestInput(text="hello")
        result = await executor.execute_async("test_command", input_data)
        
        # LangChain wraps results in RunnableLambdaOutput, check actual data
        assert hasattr(result, 'root') or hasattr(result, 'result')
        if hasattr(result, 'root'):
            assert result.root['result'] == "async: hello"
        else:
            assert result.result == "async: hello"
    
    @pytest.mark.asyncio
    async def test_execute_async_fallback_to_sync(self):
        """Test async execution falling back to sync when async is not available"""
        sync_command = RunnableLambda(lambda x: TestOutput(result=f"sync: {x.text}"))
        
        # Mock ainvoke to raise TypeError (async not supported)
        with patch.object(sync_command, 'ainvoke', side_effect=TypeError("Async not supported")):
            executor = CommandExecutor({"sync_command": sync_command})
            
            result = await executor.execute_async("sync_command", TestInput(text="test"))
            # LangChain wraps results in RunnableLambdaOutput, check actual data
            assert hasattr(result, 'root') or hasattr(result, 'result')
            if hasattr(result, 'root'):
                assert result.root['result'] == "sync: test"
            else:
                assert result.result == "sync: test"
    
    @pytest.mark.asyncio
    async def test_execute_async_command_not_found(self):
        """Test async execution with non-existent command"""
        executor = CommandExecutor({})
        
        with pytest.raises(KeyError):
            await executor.execute_async("nonexistent_command", {})
    
    @pytest.mark.asyncio
    async def test_execute_async_with_error(self):
        """Test async execution with command that raises an error"""
        async def failing_async(input_data):
            raise ValueError("Async test error")
        
        failing_command = RunnableLambda(failing_async)
        executor = CommandExecutor({"failing_command": failing_command})
        
        with pytest.raises(ValueError, match="Async test error"):
            await executor.execute_async("failing_command", TestInput(text="test"))


@pytest.mark.unit
class TestStreamExecution:
    """Test streaming command execution"""
    
    def test_stream_sync_not_implemented(self):
        """Test that sync streaming falls back gracefully"""
        sync_command = RunnableLambda(lambda x: TestOutput(result=f"sync: {x.text}"))
        executor = CommandExecutor({"test_command": sync_command})
        
        input_data = TestInput(text="hello")
        
        # Most simple commands don't support streaming, so this should fall back
        # to returning the single result
        results = list(executor.stream_sync("test_command", input_data))
        assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_stream_async_not_implemented(self):
        """Test that async streaming falls back gracefully"""
        async def async_func(input_data):
            return TestOutput(result=f"async: {input_data.text}")
        
        async_command = RunnableLambda(async_func)
        executor = CommandExecutor({"test_command": async_command})
        
        input_data = TestInput(text="hello")
        
        # Collect streaming results
        results = []
        async for result in executor.stream_async("test_command", input_data):
            results.append(result)
        
        assert len(results) >= 1
        # LangChain wraps results, check actual data
        assert hasattr(results[0], 'root') or hasattr(results[0], 'result')


@pytest.mark.unit
class TestThreadingSupport:
    """Test threading support for async execution"""
    
    def test_run_async_in_thread(self):
        """Test running async code in a separate thread"""
        async def test_coro():
            await asyncio.sleep(0.01)
            return "async result"
        
        result = CommandExecutor._run_async_in_thread(test_coro())
        assert result == "async result"
    
    def test_run_async_in_thread_with_exception(self):
        """Test that exceptions in threads are properly propagated"""
        async def failing_coro():
            raise ValueError("Thread test error")
        
        with pytest.raises(ValueError, match="Thread test error"):
            CommandExecutor._run_async_in_thread(failing_coro())