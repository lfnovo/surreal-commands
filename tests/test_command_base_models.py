"""Tests for CommandInput and CommandOutput base classes"""

import pytest
from datetime import datetime
from pydantic import BaseModel
from src.surreal_commands.core.types import CommandInput, CommandOutput, ExecutionContext


@pytest.mark.unit
class TestCommandInput:
    """Test CommandInput base class functionality"""
    
    def test_command_input_basic(self):
        """Test basic CommandInput instantiation"""
        class MyInput(CommandInput):
            message: str
            count: int = 1
        
        # Create without execution context
        input_obj = MyInput(message="test", count=2)
        assert input_obj.message == "test"
        assert input_obj.count == 2
        assert input_obj.execution_context is None
    
    def test_command_input_with_context(self):
        """Test CommandInput with execution context"""
        class MyInput(CommandInput):
            message: str
        
        # Create execution context
        ctx = ExecutionContext(
            command_id="cmd-123",
            execution_started_at=datetime.now(),
            app_name="test_app",
            command_name="test_command",
            user_context={"user_id": "user-456"}
        )
        
        # Create input with context
        input_obj = MyInput(message="test")
        input_obj.execution_context = ctx
        
        assert input_obj.execution_context == ctx
        assert input_obj.execution_context.command_id == "cmd-123"
        assert input_obj.execution_context.user_context["user_id"] == "user-456"
    
    def test_command_input_exclude_context_from_dict(self):
        """Test that execution_context is excluded from model_dump"""
        class MyInput(CommandInput):
            message: str
            flag: bool = True
        
        ctx = ExecutionContext(
            command_id="cmd-123",
            execution_started_at=datetime.now(),
            app_name="test_app",
            command_name="test_command"
        )
        
        input_obj = MyInput(message="test", flag=False)
        input_obj.execution_context = ctx
        
        # execution_context should be excluded from dict
        data = input_obj.model_dump()
        assert "execution_context" not in data
        assert data == {"message": "test", "flag": False}
    
    def test_command_input_inheritance(self):
        """Test that CommandInput can be properly inherited"""
        class ComplexInput(CommandInput):
            text: str
            numbers: list[int]
            metadata: dict[str, str]
        
        input_obj = ComplexInput(
            text="hello",
            numbers=[1, 2, 3],
            metadata={"key": "value"}
        )
        
        assert isinstance(input_obj, CommandInput)
        assert isinstance(input_obj, BaseModel)
        assert input_obj.text == "hello"
        assert input_obj.numbers == [1, 2, 3]
        assert input_obj.metadata == {"key": "value"}


@pytest.mark.unit
class TestCommandOutput:
    """Test CommandOutput base class functionality"""
    
    def test_command_output_basic(self):
        """Test basic CommandOutput instantiation"""
        class MyOutput(CommandOutput):
            result: str
            status: str = "success"
        
        # Create without metadata
        output_obj = MyOutput(result="test result")
        assert output_obj.result == "test result"
        assert output_obj.status == "success"
        assert output_obj.command_id is None
        assert output_obj.execution_time is None
        assert output_obj.execution_metadata is None
    
    def test_command_output_with_metadata(self):
        """Test CommandOutput with execution metadata"""
        class MyOutput(CommandOutput):
            result: str
        
        # Create with metadata
        output_obj = MyOutput(
            result="test result",
            command_id="cmd-123",
            execution_time=1.234,
            execution_metadata={"app": "test", "version": "1.0"}
        )
        
        assert output_obj.command_id == "cmd-123"
        assert output_obj.execution_time == 1.234
        assert output_obj.execution_metadata == {"app": "test", "version": "1.0"}
    
    def test_command_output_partial_metadata(self):
        """Test CommandOutput with partial metadata"""
        class MyOutput(CommandOutput):
            data: dict
        
        # Create with only some metadata fields
        output_obj = MyOutput(
            data={"key": "value"},
            command_id="cmd-456"
            # execution_time and execution_metadata remain None
        )
        
        assert output_obj.command_id == "cmd-456"
        assert output_obj.execution_time is None
        assert output_obj.execution_metadata is None
    
    def test_command_output_model_dump(self):
        """Test that CommandOutput includes metadata in model_dump"""
        class MyOutput(CommandOutput):
            result: str
            count: int
        
        output_obj = MyOutput(
            result="test",
            count=5,
            command_id="cmd-789",
            execution_time=0.5
        )
        
        data = output_obj.model_dump()
        assert data["result"] == "test"
        assert data["count"] == 5
        assert data["command_id"] == "cmd-789"
        assert data["execution_time"] == 0.5
        assert data["execution_metadata"] is None
    
    def test_command_output_inheritance(self):
        """Test that CommandOutput can be properly inherited"""
        class ComplexOutput(CommandOutput):
            results: list[str]
            metrics: dict[str, float]
            success: bool
        
        output_obj = ComplexOutput(
            results=["a", "b", "c"],
            metrics={"accuracy": 0.95, "speed": 1.23},
            success=True
        )
        
        assert isinstance(output_obj, CommandOutput)
        assert isinstance(output_obj, BaseModel)
        assert output_obj.results == ["a", "b", "c"]
        assert output_obj.metrics == {"accuracy": 0.95, "speed": 1.23}
        assert output_obj.success is True


@pytest.mark.unit
class TestCommandInputOutputInteraction:
    """Test interaction between CommandInput and CommandOutput"""
    
    def test_command_flow_simulation(self):
        """Simulate a command flow with input and output"""
        class ProcessInput(CommandInput):
            text: str
            options: dict
        
        class ProcessOutput(CommandOutput):
            processed_text: str
            option_count: int
        
        # Simulate receiving input
        input_obj = ProcessInput(
            text="hello world",
            options={"uppercase": True, "reverse": False}
        )
        
        # Simulate framework injecting context
        ctx = ExecutionContext(
            command_id="cmd-flow-123",
            execution_started_at=datetime.now(),
            app_name="test",
            command_name="process"
        )
        input_obj.execution_context = ctx
        
        # Simulate command processing
        processed = input_obj.text.upper() if input_obj.options.get("uppercase") else input_obj.text
        
        # Create output
        output_obj = ProcessOutput(
            processed_text=processed,
            option_count=len(input_obj.options)
        )
        
        # Simulate framework populating metadata
        output_obj.command_id = ctx.command_id
        output_obj.execution_time = 0.123
        output_obj.execution_metadata = {
            "app_name": ctx.app_name,
            "command_name": ctx.command_name
        }
        
        # Verify the flow
        assert input_obj.execution_context.command_id == "cmd-flow-123"
        assert output_obj.processed_text == "HELLO WORLD"
        assert output_obj.option_count == 2
        assert output_obj.command_id == "cmd-flow-123"
        assert output_obj.execution_time == 0.123
        assert output_obj.execution_metadata["app_name"] == "test"