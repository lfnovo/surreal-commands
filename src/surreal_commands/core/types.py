from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field


@dataclass
class ExecutionContext:
    """Context information available to commands during execution."""
    
    command_id: str
    execution_started_at: datetime
    app_name: str
    command_name: str
    user_context: Optional[Dict[str, Any]] = None


class CommandInput(BaseModel):
    """Base class for command inputs that need execution context.
    
    Commands that need access to execution context (command_id, execution time, etc.)
    should inherit from this class instead of BaseModel.
    
    Example:
        class MyCommandInput(CommandInput):
            message: str
            count: int = 1
            
        @command("my_command")
        def my_command(input_data: MyCommandInput) -> MyOutput:
            # Access execution context
            ctx = input_data.execution_context
            if ctx:
                command_id = ctx.command_id
                # ... use command_id
    """
    execution_context: Optional[ExecutionContext] = Field(
        default=None, 
        exclude=True,  # Don't include in serialization
        description="Execution context injected by the framework"
    )


class CommandOutput(BaseModel):
    """Base class for command outputs that can include execution metadata.
    
    Commands that want to include execution metadata in their outputs
    should inherit from this class instead of BaseModel.
    
    Example:
        class MyCommandOutput(CommandOutput):
            result: str
            processed_count: int
            
        # The framework will automatically populate command_id and execution_time
    """
    # Optional fields that the framework can populate
    command_id: Optional[str] = Field(
        default=None, 
        description="ID of the command that generated this output"
    )
    execution_time: Optional[float] = Field(
        default=None, 
        description="Time taken to execute the command in seconds"
    )
    execution_metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Additional execution metadata"
    )


class CommandRegistryItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    app_id: str
    name: str
    runnable: Runnable

    @property
    def input_schema(self) -> type[BaseModel]:
        return self.runnable.get_input_schema()

    @property
    def output_schema(self) -> type[BaseModel]:
        return self.runnable.get_output_schema()
