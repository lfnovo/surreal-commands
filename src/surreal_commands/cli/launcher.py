# cli.py
import typing  # Add this import at the top of cli.py
from typing import Any, Dict, Optional, cast, get_args, get_origin

import typer
from loguru import logger

from ..core.registry import registry
from ..core.service import CommandRequest, command_service
from ..core.types import CommandRegistryItem

app = typer.Typer(help="Surreal Commands CLI")


def callback(
    user_id: Optional[str] = typer.Option(
        None, "--user-id", help="User ID for context"
    ),
    scope: Optional[str] = typer.Option(
        None, "--scope", help="Data scope (e.g., health)"
    ),
):
    return {"user_id": user_id, "scope": scope}


app.callback()(callback)


def submit_command(
    app: str,
    command: CommandRegistryItem,
    args: Dict[str, Any],
    context: Dict[str, Any] | None,
):
    """Submit a command to the queue using the command service."""
    try:
        request = CommandRequest(
            app=app, command=command.name, args=args, context=context
        )

        # Submit the command to the queue
        command_id = command_service.submit_command_sync(request)

        typer.echo(f"Command submitted with ID: {command_id}")
    except Exception as e:
        typer.echo(err=True, color=True, message=f"Error: {str(e)}")
        raise typer.Exit(1)


def is_optional_type(annotation):
    """Check if a type annotation is Optional[X]"""
    origin = get_origin(annotation)
    if origin is typing.Union:
        args = get_args(annotation)
        return len(args) == 2 and args[1] is type(None)
    return False


def create_command_fn(app: str, command: CommandRegistryItem):
    # Get the Pydantic model for the command's arguments
    args_model = command.input_schema
    fields = args_model.model_fields
    # Build the parameter string for the function definition
    param_list = []
    for field_name, field_info in fields.items():
        # Get the type annotation as a string (e.g., 'bool', 'str', 'typing.Optional[str]')
        field_type_str = repr(field_info.annotation)  # e.g., "<class 'bool'>"

        # For custom complex types, use 'str' as the type for Typer
        if "surreal_commands" in field_type_str or "commands" in field_type_str:
            field_type_str = "str"
        # For datetime types, use str in CLI
        elif "datetime" in field_type_str:
            field_type_str = "str"
        # Strip the "<class '...'" part and use just the type name for basic types
        elif field_type_str.startswith("<class '") and field_type_str.endswith("'>"):
            field_type_str = field_type_str[
                8:-2
            ]  # Extract 'bool' from "<class 'bool'>"

        # Check if field is optional either by default value or by using Optional type
        from pydantic_core import PydanticUndefined

        is_optional = (
            field_info.default is not PydanticUndefined
            or field_info.default_factory is not None
            or is_optional_type(field_info.annotation)
        )

        # Set appropriate default and help text
        default_value = "None" if is_optional else "..."
        help_text = "(optional)" if is_optional else "(required)"

        # Always use Option for CLI arguments
        param_list.append(
            f"{field_name}: '{field_type_str}' = typer.Option({default_value}, '--{field_name}', help='{field_name} {help_text}')"
        )
    param_str = ", ".join(param_list)

    # Define the function code as a string
    func_code = f"""
def dynamic_command(ctx: typer.Context, {param_str}):
    kwargs = locals()
    filtered_args = {{k: v for k, v in kwargs.items() if k != 'ctx' and v is not None}}
    submit_command(app, command, filtered_args, ctx.obj)
"""

    # Execute the code to create the function
    # Import necessary modules to make them available in globals
    import datetime

    local_vars = {
        "typer": typer,
        "command": command,
        "app": app,
        "submit_command": submit_command,
        "typing": typing,  # Include typing for Optional[type] annotations
        "datetime": datetime,  # Add datetime module
    }
    exec(func_code, local_vars)
    dynamic_command = local_vars["dynamic_command"]

    # Set command metadata
    command_name = command.name.replace("_", "-")
    dynamic_command.__name__ = command_name
    dynamic_command.__doc__ = f"Run the {command.name} command from {app}"

    return dynamic_command


for app_name, commands in registry.list_commands().items():
    sub_app = typer.Typer(name=app_name, help=f"Commands for {app_name} app")
    app.add_typer(sub_app)

    for cmd_name, cmd_instance in commands.items():
        # Convert to CommandRegistryItem if not already
        if not isinstance(cmd_instance, CommandRegistryItem):
            logger.debug(f"Converting legacy command: {app_name}.{cmd_name}")
            cmd_instance = cast(
                CommandRegistryItem, registry.get_command(app_name, cmd_name)
            )

        cmd_fn = create_command_fn(app_name, cmd_instance)
        sub_app.command(name=cmd_instance.name.replace("_", "-"))(cmd_fn)

if __name__ == "__main__":
    app()
