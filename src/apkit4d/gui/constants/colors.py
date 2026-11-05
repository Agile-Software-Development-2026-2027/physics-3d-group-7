"""
Colors for GUI component execution status.
"""

from apkit4d.gui.theme.themes import DARK_STATUS_COLORS, LIGHT_STATUS_COLORS

# Muted status background colors for dark theme
DARK_STATUS_IDLE_BG: str = DARK_STATUS_COLORS.idle_bg
DARK_STATUS_PENDING_BG: str = DARK_STATUS_COLORS.pending_bg
DARK_STATUS_RUNNING_BG: str = DARK_STATUS_COLORS.running_bg
DARK_STATUS_COMPLETED_BG: str = DARK_STATUS_COLORS.completed_bg

# Muted status background and text colors for light theme
LIGHT_STATUS_IDLE_BG: str = LIGHT_STATUS_COLORS.idle_bg
LIGHT_STATUS_IDLE_TEXT: str = LIGHT_STATUS_COLORS.idle_text
LIGHT_STATUS_PENDING_BG: str = LIGHT_STATUS_COLORS.pending_bg
LIGHT_STATUS_PENDING_TEXT: str = LIGHT_STATUS_COLORS.pending_text
LIGHT_STATUS_RUNNING_BG: str = LIGHT_STATUS_COLORS.running_bg
LIGHT_STATUS_RUNNING_TEXT: str = LIGHT_STATUS_COLORS.running_text
LIGHT_STATUS_COMPLETED_BG: str = LIGHT_STATUS_COLORS.completed_bg
LIGHT_STATUS_COMPLETED_TEXT: str = LIGHT_STATUS_COLORS.completed_text
