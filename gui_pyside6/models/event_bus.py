"""
EventBus - Singleton event bus for inter-component communication.

Provides a centralized event system for managing application-wide events
using PySide6's QObject and signal/slot mechanism.
"""

from typing import Callable, Dict, Optional, Type, Any
from PySide6.QtCore import QObject, Signal, Slot


class EventBus(QObject):
    """
    Singleton event bus for cross-component communication.

    Uses PySide6's signal/slot mechanism for event broadcasting.
    Provides registration/unregistration of event handlers.
    """

    # Event signals
    data_loaded = Signal()  # Emitted when data is loaded
    filters_changed = Signal()  # Emitted when filters are modified
    sort_changed = Signal()  # Emitted when sort order changes
    table_refreshed = Signal()  # Emitted when table view is refreshed
    theme_changed = Signal()  # Emitted when theme settings change

    def __init__(self, parent: Optional[QObject] = None):
        """
        Initialize the EventBus.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)

        # Internal registry for custom event handlers
        self._custom_handlers: Dict[str, List[Callable]] = {}

    # Singleton pattern
    _instance: Optional["EventBus"] = None

    @classmethod
    def get(cls) -> "EventBus":
        """
        Get the singleton instance of EventBus.

        Returns:
            The EventBus single instance
        """
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance

    def reset(self) -> None:
        """
        Reset the singleton instance.

        Should only be called to reset state (e.g., during testing).
        """
        if cls._instance is not None:
            cls._instance = None

    # Custom event registration
    def register_event_handler(self, event_name: str, handler: Callable) -> None:
        """
        Register a handler for a custom event.

        Args:
            event_name: Name of the event to listen for
            handler: Callback function to invoke when event is emitted
        """
        if event_name not in self._custom_handlers:
            self._custom_handlers[event_name] = []

        self._custom_handlers[event_name].append(handler)

    def unregister_event_handler(self, event_name: str, handler: Callable) -> None:
        """
        Unregister a handler for a custom event.

        Args:
            event_name: Name of the event
            handler: The handler to unregister
        """
        if event_name in self._custom_handlers:
            try:
                self._custom_handlers[event_name].remove(handler)
            except ValueError:
                pass  # Handler not found, ignore

    def emit_event(self, event_name: str, *args, **kwargs) -> None:
        """
        Emit a custom event.

        Args:
            event_name: Name of the event to emit
            *args: Positional arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
        """
        if event_name in self._custom_handlers:
            for handler in self._custom_handlers[event_name]:
                try:
                    if callable(handler):
                        handler(*args, **kwargs)
                except Exception as e:
                    # Log error but continue processing other handlers
                    print(f"Event handler error for '{event_name}': {e}")

    # Convenience methods for standard events
    def on_data_loaded(self, callback: Callable) -> None:
        """
        Connect a callback to the data_loaded signal.

        Args:
            callback: Function to call when data is loaded
        """
        self.data_loaded.connect(callback)

    def on_filters_changed(self, callback: Callable) -> None:
        """
        Connect a callback to the filters_changed signal.

        Args:
            callback: Function to call when filters change
        """
        self.filters_changed.connect(callback)

    def on_sort_changed(self, callback: Callable) -> None:
        """
        Connect a callback to the sort_changed signal.

        Args:
            callback: Function to call when sort changes
        """
        self.sort_changed.connect(callback)

    def on_table_refreshed(self, callback: Callable) -> None:
        """
        Connect a callback to the table_refreshed signal.

        Args:
            callback: Function to call when table is refreshed
        """
        self.table_refreshed.connect(callback)

    def on_theme_changed(self, callback: Callable) -> None:
        """
        Connect a callback to the theme_changed signal.

        Args:
            callback: Function to call when theme changes
        """
        self.theme_changed.connect(callback)

    def disconnect(self, callback: Optional[Callable] = None) -> None:
        """
        Disconnect callbacks from all signals.

        Args:
            callback: If provided, only disconnect this callback.
                     Otherwise disconnect all callbacks.
        """
        if callback:
            # Disconnect the specific callback from all relevant signals
            try:
                self.data_loaded.disconnect(callback)
            except:
                pass
            try:
                self.filters_changed.disconnect(callback)
            except:
                pass
            try:
                self.sort_changed.disconnect(callback)
            except:
                pass
            try:
                self.table_refreshed.disconnect(callback)
            except:
                pass
            try:
                self.theme_changed.disconnect(callback)
            except:
                pass
        else:
            # Disconnect all callbacks
            self.data_loaded.disconnect()
            self.filters_changed.disconnect()
            self.sort_changed.disconnect()
            self.table_refreshed.disconnect()
            self.theme_changed.disconnect()


# Global event bus instance (alternative to singleton pattern)
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Get the global event bus instance.

    Returns:
        The EventBus singleton instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus.get()
    return _event_bus


def reset_event_bus() -> None:
    """
    Reset the global event bus instance.

    Should be called during cleanup or testing.
    """
    global _event_bus
    if _event_bus is not None:
        EventBus.reset()
        _event_bus = None
