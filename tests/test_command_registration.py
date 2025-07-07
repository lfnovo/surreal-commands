"""Tests for command registration functionality"""

import pytest
from unittest.mock import patch, Mock
from pydantic import BaseModel
from langchain_core.runnables import RunnableLambda

from src.surreal_commands.decorators import command, _detect_app_name
from src.surreal_commands.core.registry import CommandRegistry
from src.surreal_commands.core.types import CommandRegistryItem


class TestInput(BaseModel):
    text: str
    count: int = 1


class TestOutput(BaseModel):
    result: str


@pytest.fixture
def test_function():
    """A simple test function for registration"""
    def process_text(input_data: TestInput) -> TestOutput:
        return TestOutput(result=f"processed {input_data.text} x{input_data.count}")
    return process_text


@pytest.mark.unit
class TestAppNameDetection:
    """Test automatic app name detection"""
    
    def test_detect_app_name_from_module(self):
        """Test that app name is detected from module name"""
        # This is tricky to test directly, but we can test the logic
        with patch('inspect.currentframe') as mock_frame:
            mock_caller_frame = Mock()
            mock_module = Mock()
            mock_module.__name__ = "my_app.commands"
            
            mock_frame.return_value.f_back.f_back = mock_caller_frame
            with patch('inspect.getmodule', return_value=mock_module):
                app_name = _detect_app_name()
                assert app_name == "my_app"
    
    def test_detect_app_name_fallback(self):
        """Test fallback to 'app' when detection fails"""
        with patch('inspect.currentframe') as mock_frame:
            mock_caller_frame = Mock()
            mock_module = Mock()
            mock_module.__name__ = "__main__"
            
            mock_frame.return_value.f_back.f_back = mock_caller_frame
            with patch('inspect.getmodule', return_value=mock_module):
                app_name = _detect_app_name()
                assert app_name == "app"


@pytest.mark.unit
class TestCommandRegistry:
    """Test CommandRegistry functionality"""
    
    def test_registry_singleton(self):
        """Test that CommandRegistry is a singleton"""
        registry1 = CommandRegistry()
        registry2 = CommandRegistry()
        assert registry1 is registry2
    
    def test_register_command(self, clean_registry, sample_runnable):
        """Test registering a command"""
        item = clean_registry.register("test_app", "test_command", sample_runnable)
        
        assert isinstance(item, CommandRegistryItem)
        assert item.app_id == "test_app"
        assert item.name == "test_command"
        assert item.runnable is sample_runnable
    
    def test_register_duplicate_command(self, clean_registry, sample_runnable):
        """Test that duplicate commands are handled gracefully"""
        # Register the same command twice
        item1 = clean_registry.register("test_app", "test_command", sample_runnable)
        item2 = clean_registry.register("test_app", "test_command", sample_runnable)
        
        # Should return the same item
        assert item1 is item2
        
        # Should only have one command in registry
        assert len(clean_registry._items) == 1
    
    def test_get_command(self, clean_registry, sample_runnable):
        """Test retrieving a command"""
        clean_registry.register("test_app", "test_command", sample_runnable)
        
        retrieved = clean_registry.get_command("test_app", "test_command")
        assert isinstance(retrieved, CommandRegistryItem)
        assert retrieved.app_id == "test_app"
        assert retrieved.name == "test_command"
    
    def test_get_command_by_id(self, clean_registry, sample_runnable):
        """Test retrieving a command by ID"""
        clean_registry.register("test_app", "test_command", sample_runnable)
        
        retrieved = clean_registry.get_command_by_id("test_app.test_command")
        assert retrieved is not None
        assert retrieved.app_id == "test_app"
        assert retrieved.name == "test_command"
    
    def test_get_command_by_id_not_found(self, clean_registry):
        """Test retrieving a non-existent command by ID"""
        retrieved = clean_registry.get_command_by_id("nonexistent.command")
        assert retrieved is None
    
    def test_list_commands(self, clean_registry, sample_runnable):
        """Test listing all commands"""
        clean_registry.register("app1", "command1", sample_runnable)
        clean_registry.register("app1", "command2", sample_runnable)
        clean_registry.register("app2", "command1", sample_runnable)
        
        commands = clean_registry.list_commands()
        
        assert "app1" in commands
        assert "app2" in commands
        assert len(commands["app1"]) == 2
        assert len(commands["app2"]) == 1
    
    def test_get_all_commands(self, clean_registry, sample_runnable):
        """Test getting all commands as a list"""
        clean_registry.register("app1", "command1", sample_runnable)
        clean_registry.register("app2", "command2", sample_runnable)
        
        all_commands = clean_registry.get_all_commands()
        
        assert len(all_commands) == 2
        assert all(isinstance(item, CommandRegistryItem) for item in all_commands)


@pytest.mark.unit
class TestCommandDecorator:
    """Test the @command decorator"""
    
    def test_command_decorator_basic(self, clean_registry, test_function):
        """Test basic command decoration"""
        decorated = command("test_command", app="test_app")(test_function)
        
        # Function should be returned unchanged
        assert decorated is test_function
        
        # Command should be registered
        registered = clean_registry.get_command_by_id("test_app.test_command")
        assert registered is not None
        assert registered.app_id == "test_app"
        assert registered.name == "test_command"
    
    def test_command_decorator_auto_app_name(self, clean_registry, test_function):
        """Test command decoration with auto-detected app name"""
        with patch('src.surreal_commands.decorators._detect_app_name', return_value="detected_app"):
            decorated = command("test_command")(test_function)
            
            # Function should be returned unchanged
            assert decorated is test_function
            
            # Command should be registered with detected app name
            registered = clean_registry.get_command_by_id("detected_app.test_command")
            assert registered is not None
            assert registered.app_id == "detected_app"
    
    def test_command_decorator_with_registration_failure(self, clean_registry, test_function):
        """Test that decorator handles registration failures gracefully"""
        with patch.object(clean_registry, 'register', side_effect=Exception("Registration failed")):
            # Should not raise an exception
            decorated = command("test_command", app="test_app")(test_function)
            
            # Function should still be returned
            assert decorated is test_function


@pytest.mark.unit
class TestCommandRegistryItem:
    """Test CommandRegistryItem functionality"""
    
    def test_registry_item_properties(self, sample_runnable):
        """Test that registry item exposes input/output schemas"""
        item = CommandRegistryItem(
            app_id="test_app",
            name="test_command", 
            runnable=sample_runnable
        )
        
        # Should have schema properties
        assert hasattr(item, 'input_schema')
        assert hasattr(item, 'output_schema')
        
        # Schemas should be callable
        input_schema = item.input_schema
        output_schema = item.output_schema
        
        assert callable(input_schema)
        assert callable(output_schema)