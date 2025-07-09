import asyncio
import json
import os
import sys
from typing import List, Optional

import typer
from loguru import logger
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from ..repository import db_connection
from .registry import registry
from .service import command_service

# Create console instance for rich output
console = Console()

# Default number of concurrent tasks
DEFAULT_MAX_TASKS = 5

# Create typer app
app = typer.Typer(
    help="Surreal Commands Worker - Process commands from the queue",
    no_args_is_help=False,
)


def import_command_modules(modules: Optional[List[str]] = None):
    """Import specified modules to register commands"""
    if not modules:
        # Check environment variable
        env_modules = os.environ.get("SURREAL_COMMANDS_MODULES", "").strip()
        if env_modules:
            modules = [m.strip() for m in env_modules.split(",") if m.strip()]
        else:
            modules = []

    if not modules:
        logger.debug("No modules specified for import")
        return

    console.print(
        f"[bold blue]Importing command modules: {', '.join(modules)}[/bold blue]"
    )

    # Add current working directory to sys.path for relative imports
    current_dir = os.getcwd()
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
        logger.debug(f"Added current directory to sys.path: {current_dir}")

    imported_count = 0
    for module_name in modules:
        try:
            logger.debug(f"Importing module: {module_name}")
            __import__(module_name)
            imported_count += 1
            console.print(f"  ✅ Imported: {module_name}")
        except ImportError as e:
            console.print(f"  ❌ Failed to import {module_name}: {e}")
            logger.error(f"Failed to import module {module_name}: {e}")
        except Exception as e:
            console.print(f"  ❌ Error importing {module_name}: {e}")
            logger.error(f"Error importing module {module_name}: {e}")

    console.print(
        f"[bold green]Successfully imported {imported_count}/{len(modules)} modules[/bold green]"
    )


def configure_logging(debug: bool = False):
    """Configure loguru logger based on debug flag"""
    # Remove the default handler
    logger.remove()

    # Add a handler with appropriate level
    log_level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=log_level)

    if debug:
        logger.debug("Debug mode enabled - showing all log messages")
    else:
        logger.info("Debug mode disabled - showing only INFO level and above")


async def execute_command_with_semaphore(cmd_id, command_full_name, args, user_context, semaphore):
    """Execute a command with semaphore control to limit concurrency."""
    async with semaphore:
        await command_service.execute_command(cmd_id, command_full_name, args, user_context)


async def listen_for_commands(max_tasks: int) -> None:
    """
    Listen for new commands in the queue and execute them as they arrive.
    This method will run indefinitely until interrupted.
    """
    # Create a semaphore to limit concurrent tasks
    task_semaphore = asyncio.Semaphore(max_tasks)

    # Get command count for logging but only in debug mode
    commands = registry.get_all_commands()
    logger.debug(f"Listening for {len(commands)} registered commands")

    with console.status("Waiting for commands...", spinner="aesthetic"):
        async with db_connection() as db:
            # First, process any existing commands with status 'new'
            console.log("[bold]Checking for existing commands...[/bold]")
            existing_commands = await db.query(
                "SELECT * FROM command WHERE status = 'new' ORDER BY created ASC"
            )

            if existing_commands:
                console.log(
                    f"[bold green]Found {len(existing_commands)} existing command(s) to process[/bold green]"
                )
                for cmd in existing_commands:
                    if isinstance(cmd, dict) and cmd.get("status") == "new":
                        command_full_name = f"{cmd['app']}.{cmd['name']}"
                        console.rule(
                            f":stopwatch: [bold white]Processing existing command: [cyan]{cmd['app']}.[bold]{cmd['name']} [bold][magenta]{cmd['id']}"
                        )
                        console.log(f"[underline]Arguments:")
                        console.log(JSON(json.dumps(cmd["args"])))
                        console.print()

                        # Create task with semaphore to limit concurrency
                        asyncio.create_task(
                            execute_command_with_semaphore(
                                cmd["id"],
                                command_full_name,
                                cmd["args"],
                                cmd.get("context"),
                                task_semaphore,
                            )
                        )
            else:
                console.log("[dim]No existing commands found[/dim]")

            # Then start listening for new commands via LIVE query
            console.log("[bold]Starting LIVE query listener for new commands...[/bold]")
            query_uuid = await db.live("command", diff=True)
            notification_queue = await db.subscribe_live(query_uuid)

            async for cmd in notification_queue:
                try:
                    if "status" not in cmd or cmd["status"] == "new":
                        command_full_name = f"{cmd['app']}.{cmd['name']}"
                        console.rule(
                            f":stopwatch: [bold white]Started command: [cyan]{cmd['app']}.[bold]{cmd['name']} [bold][magenta]{cmd['id']}"
                        )
                        console.log(f"[underline]Arguments:")
                        console.log(JSON(json.dumps(cmd["args"])))
                        console.print()

                        # Create task with semaphore to limit concurrency
                        asyncio.create_task(
                            execute_command_with_semaphore(
                                cmd["id"],
                                command_full_name,
                                cmd["args"],
                                cmd.get("context"),
                                task_semaphore,
                            )
                        )
                except Exception as e:
                    logger.error(
                        f"Error processing command: {cmd.get('name', 'unknown')} - Args: {cmd.get('args', {})} - {e}",
                    )
                    console.log(
                        f"Error processing command: {cmd.get('name', 'unknown')} - Args: {cmd.get('args', {})} - {e}",
                    )


# This section has been removed as we now use a more direct approach


def run_worker(debug: bool, max_tasks: int, import_modules: Optional[List[str]] = None):
    """Run the worker with the specified configuration"""
    # Configure logging based on debug flag
    configure_logging(debug)

    try:
        console.clear()
        console.print(Panel("Surreal Commands Worker", border_style="green"))
        logger.info("Starting Surreal Commands worker")

        # Import command modules if specified
        import_command_modules(import_modules)

        # Get registered commands after importing modules
        commands = registry.get_all_commands()
        if not commands:
            console.print(
                "[bold yellow]Warning: No commands registered! Register commands before starting the worker.[/bold yellow]"
            )
            console.print(
                "[dim]Tip: Use --import-modules flag or set SURREAL_COMMANDS_MODULES environment variable[/dim]"
            )
            logger.warning("No commands registered in registry")
        else:
            console.print(
                f"[bold green]Using {len(commands)} registered commands[/bold green]"
            )

            # Get command information for display
            command_names = [f"{cmd.app_id}.{cmd.name}" for cmd in commands]

            # Only show the list of commands in debug mode to avoid cluttering the output
            if debug:
                logger.debug(f"Available commands: {command_names}")

        console.print(
            f"[bold green]Worker configured to handle up to {max_tasks} concurrent tasks"
        )

        # Start listening for commands
        asyncio.run(listen_for_commands(max_tasks))
    except KeyboardInterrupt:
        console.print("\nStopping worker...")
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker failed with error: {e}")
        raise


@app.command()
def start(
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
    max_tasks: int = typer.Option(
        DEFAULT_MAX_TASKS,
        "--max-tasks",
        "-m",
        help="Maximum number of concurrent tasks",
    ),
    import_modules: Optional[str] = typer.Option(
        None,
        "--import-modules",
        "-i",
        help="Comma-separated list of modules to import for command registration",
    ),
):
    """Start the worker to process commands from the queue"""
    modules_list = None
    if import_modules:
        modules_list = [m.strip() for m in import_modules.split(",") if m.strip()]
    run_worker(debug, max_tasks, modules_list)


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging"),
    max_tasks: int = typer.Option(
        DEFAULT_MAX_TASKS,
        "--max-tasks",
        "-m",
        help="Maximum number of concurrent tasks",
    ),
    import_modules: Optional[str] = typer.Option(
        None,
        "--import-modules",
        "-i",
        help="Comma-separated list of modules to import for command registration",
    ),
):
    """Surreal Commands Worker - Process commands from the queue"""
    # If no subcommand is specified, run the start command
    if ctx.invoked_subcommand is None:
        modules_list = None
        if import_modules:
            modules_list = [m.strip() for m in import_modules.split(",") if m.strip()]
        run_worker(debug=debug, max_tasks=max_tasks, import_modules=modules_list)


if __name__ == "__main__":
    app()
