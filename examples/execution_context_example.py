"""
Example showing how to use execution_context to access command_id and other execution metadata
"""

from pydantic import BaseModel
from src.surreal_commands import command, submit_command, wait_for_command_sync, ExecutionContext

class ProcessInput(BaseModel):
    message: str
    log_level: str = "INFO"

class ProcessOutput(BaseModel):
    result: str
    command_id: str
    execution_time: str
    app_info: str

@command("process_with_context")
def process_with_context(input_data: ProcessInput, execution_context: ExecutionContext) -> ProcessOutput:
    """
    Process text and include execution context information in the result.
    
    This command demonstrates accessing the command_id and other execution metadata.
    """
    # Access the command_id from execution_context
    command_id = execution_context.command_id
    
    # Access other execution metadata
    execution_time = execution_context.execution_started_at.isoformat()
    app_info = f"{execution_context.app_name}.{execution_context.command_name}"
    
    # Access user context if provided via CLI
    user_context = execution_context.user_context or {}
    user_id = user_context.get("user_id", "anonymous")
    
    # Process the message
    result = f"[{input_data.log_level}] {input_data.message} (processed by {user_id})"
    
    return ProcessOutput(
        result=result,
        command_id=command_id,
        execution_time=execution_time,
        app_info=app_info
    )

@command("process_without_context")
def process_without_context(input_data: ProcessInput) -> ProcessOutput:
    """
    Process text without execution context - demonstrates backward compatibility.
    
    This command works exactly as before, without any execution context.
    """
    result = f"[{input_data.log_level}] {input_data.message}"
    
    return ProcessOutput(
        result=result,
        command_id="unknown",
        execution_time="unknown",
        app_info="unknown"
    )

@command("analyze_with_kwargs")
def analyze_with_kwargs(input_data: ProcessInput, **kwargs) -> ProcessOutput:
    """
    Alternative way to access execution context via kwargs.
    
    This demonstrates the **kwargs pattern for accessing execution_context.
    """
    execution_context = kwargs.get("execution_context")
    
    if execution_context:
        command_id = execution_context.command_id
        execution_time = execution_context.execution_started_at.isoformat()
        app_info = f"{execution_context.app_name}.{execution_context.command_name}"
    else:
        command_id = "no_context"
        execution_time = "no_context"
        app_info = "no_context"
    
    result = f"[{input_data.log_level}] Analyzed: {input_data.message}"
    
    return ProcessOutput(
        result=result,
        command_id=command_id,
        execution_time=execution_time,
        app_info=app_info
    )

def main():
    """Example of submitting and monitoring commands with execution context"""
    print("=== Execution Context Example ===\n")
    
    # Test 1: Command with execution_context parameter
    print("1. Testing command with execution_context parameter...")
    cmd_id1 = submit_command("examples", "process_with_context", {
        "message": "Hello from context-aware command",
        "log_level": "INFO"
    })
    print(f"   Command ID: {cmd_id1}")
    
    result1 = wait_for_command_sync(cmd_id1, timeout=30)
    if result1.is_success():
        print(f"   Success: {result1.result}")
        print(f"   Command ID in result: {result1.result['command_id']}")
    else:
        print(f"   Failed: {result1.error_message}")
    
    # Test 2: Command without execution_context (backward compatibility)
    print("\n2. Testing command without execution_context...")
    cmd_id2 = submit_command("examples", "process_without_context", {
        "message": "Hello from legacy command",
        "log_level": "DEBUG"
    })
    print(f"   Command ID: {cmd_id2}")
    
    result2 = wait_for_command_sync(cmd_id2, timeout=30)
    if result2.is_success():
        print(f"   Success: {result2.result}")
    else:
        print(f"   Failed: {result2.error_message}")
    
    # Test 3: Command with kwargs approach
    print("\n3. Testing command with kwargs approach...")
    cmd_id3 = submit_command("examples", "analyze_with_kwargs", {
        "message": "Hello from kwargs command",
        "log_level": "WARN"
    })
    print(f"   Command ID: {cmd_id3}")
    
    result3 = wait_for_command_sync(cmd_id3, timeout=30)
    if result3.is_success():
        print(f"   Success: {result3.result}")
        print(f"   Command ID in result: {result3.result['command_id']}")
    else:
        print(f"   Failed: {result3.error_message}")

if __name__ == "__main__":
    main()