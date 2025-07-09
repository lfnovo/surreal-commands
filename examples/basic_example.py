"""
Basic example showing command registration and execution.

This example demonstrates:
1. Basic command definition without execution context (backward compatible)
2. Command registration using the @command decorator
3. Submitting and monitoring commands

This shows that existing commands continue to work without any changes.
"""

from pydantic import BaseModel
from src.surreal_commands import command, submit_command, wait_for_command_sync

class TextInput(BaseModel):
    text: str
    uppercase: bool = False

class TextOutput(BaseModel):
    result: str
    length: int
    processed: bool = True

@command("process_text")
def process_text(input_data: TextInput) -> TextOutput:
    """Process text with optional uppercase conversion.
    
    This is a simple command that doesn't need execution context.
    It shows backward compatibility - existing commands work without changes.
    """
    result = input_data.text.upper() if input_data.uppercase else input_data.text
    return TextOutput(
        result=result,
        length=len(result)
    )

@command("reverse_text")  
def reverse_text(input_data: TextInput) -> TextOutput:
    """Reverse the input text"""
    result = input_data.text[::-1]
    if input_data.uppercase:
        result = result.upper()
    return TextOutput(
        result=result,
        length=len(result)
    )

def main():
    """Example of submitting and monitoring commands"""
    print("=== Surreal Commands Basic Example ===\n")
    
    # Submit first command
    print("1. Submitting process_text command...")
    cmd_id1 = submit_command("examples", "process_text", {
        "text": "hello world",
        "uppercase": True
    })
    print(f"   Command ID: {cmd_id1}")
    
    # Submit second command
    print("\n2. Submitting reverse_text command...")
    cmd_id2 = submit_command("examples", "reverse_text", {
        "text": "hello world",
        "uppercase": False
    })
    print(f"   Command ID: {cmd_id2}")
    
    # Wait for first command
    print("\n3. Waiting for process_text result...")
    try:
        result1 = wait_for_command_sync(cmd_id1, timeout=30)
        if result1.is_success():
            print(f"   Success: {result1.result}")
        else:
            print(f"   Failed: {result1.error_message}")
    except TimeoutError:
        print("   Timeout waiting for command")
    
    # Wait for second command
    print("\n4. Waiting for reverse_text result...")
    try:
        result2 = wait_for_command_sync(cmd_id2, timeout=30)
        if result2.is_success():
            print(f"   Success: {result2.result}")
        else:
            print(f"   Failed: {result2.error_message}")
    except TimeoutError:
        print("   Timeout waiting for command")

if __name__ == "__main__":
    main()