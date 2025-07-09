from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict


@dataclass
class ExecutionContext:
    """Context information available to commands during execution."""
    
    command_id: str
    execution_started_at: datetime
    app_name: str
    command_name: str
    user_context: Optional[Dict[str, Any]] = None


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
