from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict


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
