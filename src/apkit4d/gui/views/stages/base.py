"""Shared protocol contract for right-panel stage inspector widgets."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StageInspectorView[P](Protocol):
    """Uniform contract for right-panel stage inspector widgets."""

    def get_params(self) -> P:
        """Read current widget values into a stage parameter object."""
        ...

    def set_params(self, params: P) -> None:
        """Programmatically populate widgets from `params` with signals blocked."""
        ...

    def set_enabled_state(self, enabled: bool) -> None:
        """Enable or disable interactive controls in the inspector."""
        ...
