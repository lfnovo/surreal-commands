"""
Advanced example showing async commands, error handling, and context
"""

import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
from src.surreal_commands import command, submit_command, get_command_status, wait_for_command

class AnalysisInput(BaseModel):
    data: List[float]
    method: str = Field(default="mean", description="Analysis method")
    threshold: Optional[float] = None

class AnalysisOutput(BaseModel):
    result: float
    method_used: str
    items_processed: int
    warnings: List[str] = []
    context_info: Optional[dict] = None

@command("analyze_data", app="analytics")
def analyze_data(input_data: AnalysisInput, context: dict = None) -> AnalysisOutput:
    """Analyze numerical data with various methods"""
    data = input_data.data
    method = input_data.method
    warnings = []
    
    if not data:
        raise ValueError("No data provided for analysis")
    
    if method == "mean":
        result = sum(data) / len(data)
    elif method == "max":
        result = max(data)
    elif method == "min":
        result = min(data)
    elif method == "sum":
        result = sum(data)
    else:
        warnings.append(f"Unknown method '{method}', using mean instead")
        result = sum(data) / len(data)
        method = "mean"
    
    # Apply threshold if specified
    if input_data.threshold is not None:
        if result > input_data.threshold:
            warnings.append(f"Result {result} exceeds threshold {input_data.threshold}")
    
    return AnalysisOutput(
        result=result,
        method_used=method,
        items_processed=len(data),
        warnings=warnings,
        context_info=context
    )

@command("failing_command", app="test")
def failing_command(input_data: dict) -> dict:
    """A command that always fails for testing error handling"""
    raise RuntimeError("This command always fails for testing purposes")

async def async_example():
    """Example using async API"""
    print("=== Surreal Commands Advanced Example (Async) ===\n")
    
    # Submit analysis command with context
    print("1. Submitting analysis command with context...")
    cmd_id = submit_command(
        "analytics", 
        "analyze_data", 
        {
            "data": [1.5, 2.3, 4.1, 3.7, 2.9],
            "method": "mean",
            "threshold": 3.0
        },
        context={"user_id": "user123", "session": "test_session"}
    )
    print(f"   Command ID: {cmd_id}")
    
    # Monitor status periodically
    print("\n2. Monitoring command status...")
    for i in range(5):
        await asyncio.sleep(1)
        try:
            status = await get_command_status(cmd_id)
            print(f"   Check {i+1}: {status.status}")
            if status.is_complete():
                if status.is_success():
                    print(f"   Final result: {status.result}")
                else:
                    print(f"   Command failed: {status.error_message}")
                break
        except Exception as e:
            print(f"   Error checking status: {e}")
    
    # Test error handling
    print("\n3. Testing error handling...")
    fail_cmd_id = submit_command("test", "failing_command", {"test": "data"})
    try:
        result = await wait_for_command(fail_cmd_id, timeout=30)
        if result.is_success():
            print("   Unexpected success!")
        else:
            print(f"   Expected failure: {result.error_message}")
    except Exception as e:
        print(f"   Exception during wait: {e}")

def sync_example():
    """Example using sync API"""
    print("=== Surreal Commands Advanced Example (Sync) ===\n")
    
    # Submit multiple analysis commands
    commands = [
        {"data": [1, 2, 3, 4, 5], "method": "mean"},
        {"data": [10, 20, 30], "method": "max"},
        {"data": [1.1, 2.2, 3.3], "method": "unknown_method"}  # Will trigger warning
    ]
    
    cmd_ids = []
    for i, cmd_args in enumerate(commands, 1):
        print(f"{i}. Submitting analysis command (method: {cmd_args['method']})...")
        cmd_id = submit_command("analytics", "analyze_data", cmd_args)
        cmd_ids.append(cmd_id)
        print(f"   Command ID: {cmd_id}")
    
    # Wait for all results
    print(f"\n4. Waiting for {len(cmd_ids)} commands to complete...")
    for i, cmd_id in enumerate(cmd_ids, 1):
        try:
            result = wait_for_command_sync(cmd_id, timeout=30)
            if result.is_success():
                output = result.result
                print(f"   Command {i}: {output['method_used']} = {output['result']}")
                if output['warnings']:
                    print(f"     Warnings: {', '.join(output['warnings'])}")
            else:
                print(f"   Command {i} failed: {result.error_message}")
        except TimeoutError:
            print(f"   Command {i} timed out")

def main():
    """Run examples"""
    try:
        # Run sync example
        sync_example()
        
        print("\n" + "="*50 + "\n")
        
        # Run async example
        asyncio.run(async_example())
        
    except Exception as e:
        print(f"Error running examples: {e}")

if __name__ == "__main__":
    main()