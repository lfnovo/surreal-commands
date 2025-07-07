"""Worker CLI entry point for surreal-commands-worker command"""

import typer
from ..core.worker import app as worker_app


def main():
    """Main entry point for surreal-commands-worker CLI command"""
    worker_app()


if __name__ == "__main__":
    main()