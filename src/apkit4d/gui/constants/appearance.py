"""
Sizes of the window and of its parts, in pixels, and opacity of the splitter handles.
"""

# window
WINDOW_WIDTH: int = 1200
WINDOW_HEIGHT: int = 800

# columns, from left to right: left panel, center panel, right panel
SIDE_PANEL_WIDTH: int = 200  # initial width of the side columns
SIDE_PANEL_MIN_WIDTH: int = 120  # narrower than this, a side column collapses
COLUMN_SIZES: tuple[int, int, int] = (
    SIDE_PANEL_WIDTH,
    WINDOW_WIDTH - 2 * SIDE_PANEL_WIDTH,
    SIDE_PANEL_WIDTH,
)
COLUMN_COLLAPSIBLE: tuple[bool, bool, bool] = (True, False, True)  # the 3D view never disappears
COLUMN_STRETCH: tuple[int, int, int] = (0, 1, 0)  # when the window is resized, only the center changes

# splitter handles: the whole strip can be dragged, the grip in its middle shows where to grab
HANDLE_WIDTH: int = 18
HANDLE_LINE_WIDTH: int = 1
GRIP_THICKNESS: int = 16  # size of the grip across the strip, it must fit in HANDLE_WIDTH
GRIP_LENGTH: int = 40  # size of the grip along the strip
GRIP_RADIUS: int = 5  # roundness of the corners of the grip
GRIP_ARROW_WIDTH: int = 5  # how far each arrow extends across the strip
GRIP_ARROW_HEIGHT: int = 10  # height of the base of each arrow, along the strip
GRIP_ARROW_GAP: int = 2  # space between the two arrows

# opacity of the handle parts while the mouse is away, from 0 (invisible) to 255 (solid)
HANDLE_LINE_OPACITY: int = 50
GRIP_OPACITY: int = 90
GRIP_ARROW_OPACITY: int = 210
