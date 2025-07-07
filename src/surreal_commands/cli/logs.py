import asyncio

import click
from rich.console import Console
from rich.json import JSON
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from ..repository import db_connection

console = Console()
import json


async def logs_main():
    console.clear()
    console.print(Panel("Surreal Commands Events"))
    with console.status("Waiting for logs...", spinner="aesthetic"):
        async with db_connection() as db:
            query_uuid = await db.live("system_event")
            notification_queue = await db.subscribe_live(query_uuid)

            async for event in notification_queue:
                console.rule(
                    f"[white]:gear: [bold white]Event: [cyan]{event['app']}.[bold]{event['name']}"
                )
                event["id"] = str(event["id"])
                console.log(JSON(json.dumps(event["data"])))


# Click command to launch the application
@click.command()
def cli():
    """CLI application with a table of latest commands and a live event stream."""
    asyncio.run(logs_main())


def main():
    """Main entry point for surreal-commands-logs CLI command"""
    cli()


if __name__ == "__main__":
    main()
