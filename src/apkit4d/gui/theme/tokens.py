"""
Design tokens: the sizes, fonts and color mixes that every component of the GUI shares.

The values come from the playback bar, the reference look of the application. A component that
follows these tokens looks like it belongs to the same family, in every theme.

Colors are not here: they come from the palette of the active theme, and `theme.colors` derives
the shades of the components (borders, hover, disabled) with the mixes defined below.

Sizes are in pixels, fonts in points. Sizes that belong to one component only (the width of the
speed field, the geometry of the slider bubble, ...) stay in `constants.appearance`.
"""

# corners
BUTTON_RADIUS: int = 9  # roundness of buttons, fields and every other control
SMALL_RADIUS: int = 7  # roundness of small surfaces drawn over the content, such as the slider bubble

# controls
CONTROL_HEIGHT: int = 32  # height of buttons and fields
CONTROL_PADDING: int = 12  # on the left and on the right of the content of a control with a text
ICON_SIZE: int = 20  # icon of a button with a text
SMALL_ICON_SIZE: int = 18  # icon of a small button inside another control, such as the - and + of a field
ICON_GAP: int = 6  # between the icon and the text of a button

# spacing between the parts of a component
SPACING: int = 8  # between the items of a row
ROW_SPACING: int = 10  # between two rows
GROUP_SPACING: int = 8  # extra space on both sides of a divider that separates two groups of items

# keyboard focus
FOCUS_RING_WIDTH: int = 2  # ring around a control reached with the keyboard
FOCUS_RING_LIGHTEN: float = 0.6  # the ring of a primary button is the accent color mixed with white

# fonts
FONT_POINTS: float = 11  # text inside the controls
LARGE_FONT_POINTS: float = 13  # values that must be read at a glance, such as the frame counter
SMALL_FONT_POINTS: float = 9.5  # short hints drawn over the content, such as the slider bubble

# shades, as a mix of the window color (0) and of the text color (1)
BORDER_MIX: float = 0.16  # border of a control
DISABLED_BORDER_MIX: float = 0.08  # border of a disabled control
HOVER_MIX: float = 0.10  # background of a control while the mouse is over it (mixed with the button color)
GROOVE_MIX: float = 0.20  # track of a slider
DISABLED_GROOVE_MIX: float = 0.14  # track of a disabled slider
DISABLED_RING_MIX: float = 0.24  # handle of a disabled slider
MUTED_MIX: float = 0.62  # text of secondary importance

# shades of the accent color, used by the primary button
ACCENT_HOVER_MIX: float = 0.15  # mix of the accent color (0) and of white (1) while the mouse is over it
ACCENT_PRESSED_DARKER: int = 115  # percentage of darkening of the accent color while it is pressed
