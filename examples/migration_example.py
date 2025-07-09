"""
Migration example showing how to update commands from the OLD pattern to the NEW pattern.

This guide helps users migrate their existing commands that use execution_context
as a parameter to the new CommandInput/CommandOutput base class pattern.
"""

from pydantic import BaseModel
from typing import Optional
from src.surreal_commands import (
    command, submit_command, wait_for_command_sync,
    ExecutionContext, CommandInput, CommandOutput
)

# ============================================================================
# OLD PATTERN (This will cause the error you encountered)
# ============================================================================

# DON'T DO THIS ANYMORE - This pattern causes the error:
# "generate_podcast_command() missing 1 required positional argument: 'execution_context'"

class OldProcessInput(BaseModel):
    message: str
    uppercase: bool = False

class OldProcessOutput(BaseModel):
    result: str
    command_id: str
    processing_time: float

# This OLD pattern will fail with RunnableLambda
# @command("old_process_command")
# async def old_process_command(
#     input_data: OldProcessInput, 
#     execution_context: ExecutionContext  # <-- This causes the error!
# ) -> OldProcessOutput:
#     """OLD PATTERN - DON'T USE THIS"""
#     command_id = execution_context.command_id
#     # ... processing logic ...
#     return OldProcessOutput(
#         result="processed",
#         command_id=command_id,
#         processing_time=0.1
#     )

# ============================================================================
# NEW PATTERN (Recommended approach)
# ============================================================================

# DO THIS INSTEAD - Use CommandInput and CommandOutput base classes

class NewProcessInput(CommandInput):  # <-- Inherit from CommandInput
    message: str
    uppercase: bool = False

class NewProcessOutput(CommandOutput):  # <-- Inherit from CommandOutput
    result: str
    # command_id, execution_time, and execution_metadata are inherited

@command("new_process_command")
async def new_process_command(
    input_data: NewProcessInput  # <-- Only one parameter!
) -> NewProcessOutput:
    """NEW PATTERN - This is the recommended approach"""
    
    # Access execution context from the input object
    ctx = input_data.execution_context
    
    if ctx:
        command_id = ctx.command_id
        app_name = ctx.app_name
        # Use the context as needed
        print(f"Processing command {command_id} from app {app_name}")
    
    # Process the message
    result = input_data.message.upper() if input_data.uppercase else input_data.message
    
    # Return the output - framework auto-populates command_id and execution_time
    return NewProcessOutput(
        result=result
        # command_id and execution_time are automatically set!
    )

# ============================================================================
# REAL WORLD EXAMPLE: Migrating your podcast command
# ============================================================================

# BEFORE (your current failing code):
class PodcastGenerationInputOld(BaseModel):
    episode_profile_name: str
    episode_name: str
    content: str
    briefing_suffix: Optional[str] = None

# @command("generate_podcast", app="open_notebook")
# async def generate_podcast_command_old(
#     input_data: PodcastGenerationInputOld, 
#     execution_context: ExecutionContext  # <-- This causes the error!
# ) -> PodcastGenerationOutput:
#     command_id = execution_context.command_id
#     # ... rest of implementation

# AFTER (fixed version):
class PodcastGenerationInputNew(CommandInput):  # <-- Change to inherit from CommandInput
    episode_profile_name: str
    episode_name: str
    content: str
    briefing_suffix: Optional[str] = None

class PodcastGenerationOutputNew(CommandOutput):  # <-- Inherit from CommandOutput
    success: bool
    episode_id: Optional[str] = None
    audio_file_path: Optional[str] = None
    transcript: Optional[dict] = None
    outline: Optional[dict] = None
    processing_time: float
    error_message: Optional[str] = None

@command("generate_podcast_new", app="open_notebook")
async def generate_podcast_command_new(
    input_data: PodcastGenerationInputNew  # <-- Only one parameter!
) -> PodcastGenerationOutputNew:
    """Fixed version using the new pattern"""
    
    # Access execution context from input
    ctx = input_data.execution_context
    if ctx:
        command_id = ctx.command_id
        # Use command_id as before
        print(f"Generating podcast for command: {command_id}")
    
    # ... rest of your implementation remains the same
    
    # Return output - command_id and execution_time are auto-populated
    return PodcastGenerationOutputNew(
        success=True,
        episode_id="episode-123",
        processing_time=10.5
        # command_id is automatically set by the framework!
    )

# ============================================================================
# TESTING THE MIGRATION
# ============================================================================

def main():
    """Test the migrated commands"""
    print("=== Migration Example ===\n")
    
    # Test the new pattern command
    print("Testing NEW pattern command...")
    cmd_id = submit_command("examples", "new_process_command", {
        "message": "Hello World",
        "uppercase": True
    })
    print(f"Submitted command: {cmd_id}")
    
    result = wait_for_command_sync(cmd_id, timeout=30)
    if result.is_success():
        print(f"Success! Result: {result.result}")
        print(f"Auto-populated command_id: {result.result.get('command_id')}")
        print(f"Auto-populated execution_time: {result.result.get('execution_time')} seconds")
    else:
        print(f"Failed: {result.error_message}")

if __name__ == "__main__":
    main()