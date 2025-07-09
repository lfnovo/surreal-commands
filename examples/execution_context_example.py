"""
Example showing how to use CommandInput and CommandOutput base classes for execution context.

This example demonstrates the NEW recommended pattern for accessing execution context.
"""

from pydantic import BaseModel
from src.surreal_commands import (
    command, submit_command, wait_for_command_sync, 
    CommandInput, CommandOutput
)

# New pattern: Inherit from CommandInput to access execution context
class ProcessInput(CommandInput):
    message: str
    log_level: str = "INFO"

# New pattern: Inherit from CommandOutput to get automatic metadata population
class ProcessOutput(CommandOutput):
    result: str
    app_info: str

@command("process_with_context")
def process_with_context(input_data: ProcessInput) -> ProcessOutput:
    """
    Process text and include execution context information in the result.
    
    This command demonstrates the NEW pattern for accessing execution context
    by inheriting from CommandInput and CommandOutput base classes.
    """
    # Access execution context from the input object
    ctx = input_data.execution_context
    
    if ctx:
        # Access execution metadata
        app_info = f"{ctx.app_name}.{ctx.command_name}"
        
        # Access user context if provided via CLI
        user_context = ctx.user_context or {}
        user_id = user_context.get("user_id", "anonymous")
    else:
        # Handle case where no context is available (shouldn't happen in normal operation)
        app_info = "no-context"
        user_id = "anonymous"
    
    # Process the message
    result = f"[{input_data.log_level}] {input_data.message} (processed by {user_id})"
    
    # Return ProcessOutput - the framework will automatically populate:
    # - command_id (from execution context)
    # - execution_time (measured by the framework)
    # - execution_metadata (additional context info)
    return ProcessOutput(
        result=result,
        app_info=app_info
        # command_id, execution_time, and execution_metadata are auto-populated!
    )

# For comparison: command without CommandInput/CommandOutput base classes
class SimpleInput(BaseModel):
    text: str

class SimpleOutput(BaseModel):
    result: str

@command("simple_command")
def simple_command(input_data: SimpleInput) -> SimpleOutput:
    """
    Simple command without execution context.
    
    This shows that you can still use regular BaseModel classes
    when you don't need execution context.
    """
    return SimpleOutput(result=f"Processed: {input_data.text}")

# Advanced: Using only CommandOutput to get execution metadata in output
@command("track_output_only")
def track_output_only(input_data: SimpleInput) -> ProcessOutput:
    """
    Command that uses CommandOutput to include execution metadata.
    
    This shows you can use CommandOutput even if your input doesn't
    inherit from CommandInput. Useful when you only want to track
    execution metadata in the output.
    """
    result = f"Tracked: {input_data.text}"
    
    return ProcessOutput(
        result=result,
        app_info="tracking-example"
        # command_id and execution_time will be auto-populated
    )

def main():
    """Example of submitting and monitoring commands with execution context"""
    print("=== Execution Context Example (NEW Pattern) ===\n")
    
    # Test 1: Command with CommandInput/CommandOutput (NEW PATTERN)
    print("1. Testing command with CommandInput/CommandOutput...")
    cmd_id1 = submit_command("examples", "process_with_context", {
        "message": "Hello from context-aware command",
        "log_level": "INFO"
    })
    print(f"   Command ID: {cmd_id1}")
    
    result1 = wait_for_command_sync(cmd_id1, timeout=30)
    if result1.is_success():
        print(f"   Success: {result1.result}")
        print(f"   Auto-populated command_id: {result1.result.get('command_id')}")
        print(f"   Auto-populated execution_time: {result1.result.get('execution_time')} seconds")
    else:
        print(f"   Failed: {result1.error_message}")
    
    # Test 2: Simple command without execution context
    print("\n2. Testing simple command (no context needed)...")
    cmd_id2 = submit_command("examples", "simple_command", {
        "text": "Hello from simple command"
    })
    print(f"   Command ID: {cmd_id2}")
    
    result2 = wait_for_command_sync(cmd_id2, timeout=30)
    if result2.is_success():
        print(f"   Success: {result2.result}")
    else:
        print(f"   Failed: {result2.error_message}")
    
    # Test 3: Command with CommandOutput only (tracking output metadata)
    print("\n3. Testing command with CommandOutput only...")
    cmd_id3 = submit_command("examples", "track_output_only", {
        "text": "Track this execution"
    })
    print(f"   Command ID: {cmd_id3}")
    
    result3 = wait_for_command_sync(cmd_id3, timeout=30)
    if result3.is_success():
        print(f"   Success: {result3.result}")
        print(f"   Auto-populated command_id: {result3.result.get('command_id')}")
        print(f"   Auto-populated execution_time: {result3.result.get('execution_time')} seconds")
    else:
        print(f"   Failed: {result3.error_message}")

if __name__ == "__main__":
    main()