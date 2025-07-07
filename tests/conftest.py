"""Pytest configuration and fixtures for surreal-commands tests"""

import pytest
from unittest.mock import Mock
from pydantic import BaseModel
from langchain_core.runnables import RunnableLambda

from src.surreal_commands.core.registry import CommandRegistry


class TestInput(BaseModel):
    """Test input model for testing"""
    message: str
    count: int = 1


class TestOutput(BaseModel):
    """Test output model for testing"""
    result: str
    processed: bool = True


@pytest.fixture
def test_input():
    """Fixture for test input data"""
    return TestInput(message="test message", count=2)


@pytest.fixture
def test_output():
    """Fixture for test output data"""
    return TestOutput(result="processed test message", processed=True)


@pytest.fixture
def mock_db():
    """Fixture for mocked database connection"""
    mock_db = Mock()
    mock_db.signin = Mock()
    mock_db.use = Mock()
    mock_db.create = Mock()
    mock_db.query = Mock()
    mock_db.merge = Mock()
    mock_db.close = Mock()
    return mock_db


@pytest.fixture
def sample_command_function():
    """Fixture for a sample command function"""
    def test_command(input_data: TestInput) -> TestOutput:
        result = f"processed {input_data.message} x{input_data.count}"
        return TestOutput(result=result)
    return test_command


@pytest.fixture
def sample_async_command_function():
    """Fixture for a sample async command function"""
    async def test_async_command(input_data: TestInput) -> TestOutput:
        result = f"async processed {input_data.message} x{input_data.count}"
        return TestOutput(result=result)
    return test_async_command


@pytest.fixture
def sample_runnable(sample_command_function):
    """Fixture for a sample LangChain runnable"""
    return RunnableLambda(sample_command_function)


@pytest.fixture
def clean_registry():
    """Fixture that provides a clean registry for each test"""
    # Clear the registry before each test
    registry = CommandRegistry()
    registry._items = []
    registry._commands = {}
    registry._apps = {}
    yield registry
    # Clean up after test
    registry._items = []
    registry._commands = {}
    registry._apps = {}