# Surreal Commands Examples

This document provides comprehensive examples of using the Surreal Commands library for different scenarios.

## Installation

```bash
pip install surreal-commands
```

## Basic Usage

### 1. Define Commands with Decorators

```python
# my_app/tasks.py
from surreal_commands import command
from pydantic import BaseModel

class TextInput(BaseModel):
    text: str
    uppercase: bool = False

class TextOutput(BaseModel):
    result: str
    length: int

@command("process_text")  # Auto-detects app name as "my_app"
def process_text(input_data: TextInput) -> TextOutput:
    result = input_data.text.upper() if input_data.uppercase else input_data.text
    return TextOutput(result=result, length=len(result))

@command("analyze", app="analytics")  # Override app name
def analyze_data(input_data: TextInput) -> TextOutput:
    return TextOutput(
        result=f"Analyzed: {input_data.text}",
        length=len(input_data.text)
    )
```

### 2. Submit and Monitor Commands

```python
from surreal_commands import submit_command, wait_for_command_sync

# Submit a command
cmd_id = submit_command("my_app", "process_text", {
    "text": "hello world",
    "uppercase": True
})

print(f"Command submitted: {cmd_id}")

# Wait for completion
result = wait_for_command_sync(cmd_id, timeout=30)
if result.is_success():
    print(f"Result: {result.result}")
else:
    print(f"Failed: {result.error_message}")
```

### 3. Start the Worker

```bash
# Start the worker with module imports
surreal-commands-worker start --import-modules "my_app.tasks"

# Using environment variable
export SURREAL_COMMANDS_MODULES="my_app.tasks"
surreal-commands-worker start

# With debug logging
surreal-commands-worker start --debug --import-modules "my_app.tasks"

# With custom task limit
surreal-commands-worker start --max-tasks 10 --import-modules "my_app.tasks"

# Import multiple modules
surreal-commands-worker start --import-modules "my_app.tasks,analytics.commands"
```

## Advanced Usage

### Async Command Handling

```python
import asyncio
from surreal_commands import submit_command, get_command_status, wait_for_command

async def async_example():
    # Submit command
    cmd_id = submit_command("analytics", "analyze", {"text": "data"})
    
    # Monitor status
    status = await get_command_status(cmd_id)
    print(f"Status: {status.status}")
    
    # Wait for completion
    result = await wait_for_command(cmd_id, timeout=60)
    if result.is_success():
        print(f"Result: {result.result}")

# Run async
asyncio.run(async_example())
```

### Error Handling

```python
from surreal_commands import submit_command, wait_for_command_sync, CommandStatus

@command("failing_task")
def failing_task(input_data: dict) -> dict:
    raise ValueError("Something went wrong")

# Submit and handle errors
cmd_id = submit_command("test", "failing_task", {"data": "test"})

try:
    result = wait_for_command_sync(cmd_id, timeout=30)
    if result.status == CommandStatus.FAILED:
        print(f"Task failed: {result.error_message}")
except TimeoutError:
    print("Task timed out")
```

### Context and Metadata

```python
@command("contextual_task")
def contextual_task(input_data: dict, context: dict = None) -> dict:
    user_id = context.get("user_id") if context else "unknown"
    return {"processed_by": user_id, "data": input_data}

# Submit with context
cmd_id = submit_command(
    "my_app", 
    "contextual_task", 
    {"message": "hello"},
    context={"user_id": "user123", "session": "abc"}
)
```

### Direct Registry Usage

```python
from surreal_commands import registry
from langchain_core.runnables import RunnableLambda

def my_function(data):
    return {"processed": data}

# Register manually
my_runnable = RunnableLambda(my_function)
registry.register("manual_app", "my_command", my_runnable)

# List all commands
commands = registry.list_commands()
for app_name, app_commands in commands.items():
    print(f"App: {app_name}")
    for cmd_name in app_commands:
        print(f"  Command: {cmd_name}")
```

## CLI Tools

### Worker Management

```bash
# Start worker with command imports
surreal-commands-worker start --import-modules "my_app.tasks"

# Using environment variable
export SURREAL_COMMANDS_MODULES="my_app.tasks"
surreal-commands-worker start

# Start with specific configuration
surreal-commands-worker start --debug --max-tasks 20 --import-modules "my_app.tasks"
```

### Monitoring

```bash
# View command dashboard
surreal-commands-dashboard

# View real-time logs
surreal-commands-logs
```

## Environment Configuration

Create a `.env` file with SurrealDB configuration:

```env
# SurrealDB Configuration
SURREAL_URL=ws://localhost:8000/rpc
SURREAL_USER=root
SURREAL_PASSWORD=root
SURREAL_NAMESPACE=surreal_commands
SURREAL_DATABASE=commands
```

## Project Structure

```
your_project/
├── my_app/
│   ├── __init__.py
│   └── tasks.py          # Command definitions
├── main.py               # Application entry point
├── .env                  # Environment variables
└── requirements.txt      # Dependencies
```

## Testing Your Commands

```python
# test_commands.py
from surreal_commands import registry, submit_command, execute_command_sync

def test_process_text():
    # Import your commands to register them
    import my_app.tasks
    
    # Test command execution
    result = execute_command_sync(
        "my_app", 
        "process_text", 
        {"text": "test", "uppercase": True},
        timeout=10
    )
    
    assert result.is_success()
    assert result.result["result"] == "TEST"
    print("✅ Test passed!")

if __name__ == "__main__":
    test_process_text()
```

## Best Practices

1. **Command Naming**: Use descriptive names and follow snake_case convention
2. **Type Safety**: Always use Pydantic models for input/output validation
3. **Error Handling**: Implement proper error handling in your commands
4. **Context Usage**: Use context for user identification and session data
5. **Testing**: Write tests for your commands before deploying
6. **Monitoring**: Use the CLI tools to monitor command execution

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure to import your command modules before starting the worker
2. **Database Connection**: Verify SurrealDB is running and environment variables are correct
3. **Command Not Found**: Check that commands are properly registered with `@command` decorator
4. **Timeout Issues**: Increase timeout values for long-running commands

### Debug Mode

Enable debug logging to see detailed information:

```bash
surreal-commands-worker start --debug
```

Or in Python:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Examples in This Repository

- `examples/basic_example.py` - Simple command registration and execution
- `examples/advanced_example.py` - Async handling, error cases, and context
- `examples/test_integration.py` - Integration tests for library functionality

Run examples:

```bash
# Basic example
python examples/basic_example.py

# Advanced example  
python examples/advanced_example.py

# Integration test
python examples/test_integration.py
```