"""Registry for command management"""

from typing import Dict, List, Optional, Union

from langchain_core.runnables import Runnable
from loguru import logger

from .types import CommandRegistryItem


class CommandRegistry:
    """
    Singleton registry for command management.
    This class maintains a registry of all commands available in the application.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            logger.debug("Creating CommandRegistry singleton instance")
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not self._initialized:
            logger.debug("Initializing CommandRegistry")
            self._items: List[CommandRegistryItem] = []
            # Backward compatibility
            self._commands: Dict[str, Runnable] = {}
            self._apps: Dict[str, Dict[str, Runnable]] = {}
            self._initialized = True

    def register(self, app: str, name: str, command: Runnable) -> CommandRegistryItem:
        """Register a command under an app namespace"""
        # Check if command is already registered to avoid duplicates
        for item in self._items:
            if item.app_id == app and item.name == name:
                logger.debug(f"Command {app}.{name} already registered, skipping")
                return item

        # Create new registry item
        item = CommandRegistryItem(app_id=app, name=name, runnable=command)
        self._items.append(item)

        # Maintain backward compatibility
        if app not in self._apps:
            self._apps[app] = {}

        self._apps[app][name] = command
        self._commands[f"{app}.{name}"] = command

        logger.debug(f"Registered command {app}.{name}")
        return item

    def get_command(self, app: str, name: str) -> Union[CommandRegistryItem, Runnable]:
        """Get a command by app and name"""
        # Try to find in new structure first
        for item in self._items:
            if item.app_id == app and item.name == name:
                return item

        # Fallback to old structure
        return self._apps[app][name]

    def get_command_by_id(self, command_id: str) -> Optional[CommandRegistryItem]:
        """Get a command by its full ID (app.name)"""
        app_id, name = command_id.split(".", 1)
        for item in self._items:
            if item.app_id == app_id and item.name == name:
                return item
        return None

    def list_commands(
        self,
    ) -> Dict[str, Dict[str, Union[CommandRegistryItem, Runnable]]]:
        """Get all registered commands grouped by app"""
        # If using new structure primarily
        if self._items:
            result: Dict[str, Dict[str, Union[CommandRegistryItem, Runnable]]] = {}
            for item in self._items:
                if item.app_id not in result:
                    result[item.app_id] = {}
                result[item.app_id][item.name] = item
            return result

        # Fallback to old structure
        return self._apps

    def get_all_commands(self) -> List[CommandRegistryItem]:
        """Get all registered commands as a list of CommandRegistryItem"""
        return self._items


# Initialize and export the registry singleton
registry = CommandRegistry()
