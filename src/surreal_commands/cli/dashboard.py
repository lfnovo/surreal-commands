import asyncio
import time

import click
from loguru import logger
from pydantic import BaseModel
from rich.live import Live
from rich.table import Table

from ..repository import db_connection


def get_status_emoji(status: str) -> str:
    """Get emoji for status"""
    return {"new": "⚪", "running": "🟡", "completed": "🟢", "error": "🔴"}.get(
        status, "❓"
    )


async def dashboard_main():
    table = Table(expand=True, title="Listening to events")
    table.add_column("Event ID")
    table.add_column("Status")
    table.add_column("App Name")
    table.add_column("Command Name")
    # table.add_column("Timestamp")

    with Live(table, refresh_per_second=3):
        async with db_connection() as db:
            commands = await db.query("select * from command")
            for command in commands:
                table.add_row(
                    str(command["id"]),
                    get_status_emoji(command.get("status", "Unknown"))
                    + " "
                    + command.get("status", "Unknown"),
                    command.get("app", "Unknown"),
                    command.get("name", "Unknown"),
                    # )"name"],
                    # naturaltime(command["updated"]),
                )


# Click command to launch the application
@click.command()
def cli():
    """CLI application with a table of latest commands and a live event stream."""
    asyncio.run(dashboard_main())


def main():
    """Main entry point for surreal-commands-dashboard CLI command"""
    cli()


if __name__ == "__main__":
    main()
