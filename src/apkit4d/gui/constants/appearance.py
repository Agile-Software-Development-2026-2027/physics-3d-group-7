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

# playback bar
BAR_MARGINS: tuple[int, int, int, int] = (18, 0, 18, 14)  # left, top, right, bottom
BAR_ROWS_SPACING: int = 10  # between the slider and the row of buttons
BAR_ITEMS_SPACING: int = 8  # between the items of a row
TRANSPORT_BUTTON_SIZE: int = 36
PLAY_BUTTON_SIZE: int = 44
TRANSPORT_ICON_SIZE: int = 20
PLAY_ICON_SIZE: int = 22
BUTTON_RADIUS: int = 9
FOCUS_RING_WIDTH: int = 2  # ring around a button reached with the keyboard
FOCUS_RING_LIGHTEN: float = 0.6  # the ring of the accent button is the accent color mixed with white
SLIDER_HEIGHT: int = 22
COUNTER_FONT_POINTS: float = 13
COUNTER_SPACING: int = 10  # extra space between the buttons and the counter
COUNTER_VERTICAL_PADDING: int = 6
SLIDER_PADDING: int = 9  # space between the ends of the groove and the sides of the widget
SLIDER_GROOVE_HEIGHT: int = 6
SLIDER_HANDLE_RADIUS: float = 7.2
SLIDER_HANDLE_RING: float = 2.6

# colors of the playback bar, as a mix of the window color (0) and of the text color (1)
BORDER_MIX: float = 0.16
DISABLED_BORDER_MIX: float = 0.08
HOVER_MIX: float = 0.10
GROOVE_MIX: float = 0.20
COUNTER_MUTED_MIX: float = 0.62  # the total of the counter is dimmed
DISABLED_GROOVE_MIX: float = 0.14
DISABLED_RING_MIX: float = 0.24
ACCENT_HOVER_MIX: float = 0.15  # mix of the accent color (0) and of white (1) while the mouse is over it
ACCENT_PRESSED_DARKER: int = 115  # percentage of darkening of the accent color while it is pressed

# preview that follows the mouse on the slider: a marker on the groove and a bubble above it
HOVER_MARKER_WIDTH: int = 2
HOVER_MARKER_HALF_HEIGHT: int = 8
HOVER_MARKER_OPACITY: int = 230  # from 0 (invisible) to 255 (solid)
BUBBLE_HEIGHT: int = 24  # of the body of the bubble, without the pointer
BUBBLE_POINTER_HEIGHT: int = 6
BUBBLE_POINTER_WIDTH: int = 10
BUBBLE_GAP: int = 3  # between the tip of the pointer and the groove
BUBBLE_RADIUS: int = 7
BUBBLE_PADDING: int = 11  # on the left and on the right of the text
BUBBLE_FONT_POINTS: float = 9.5
# the slider keeps some room above its groove, where the bubble of the preview is drawn
SLIDER_HEADROOM: int = (
    BUBBLE_HEIGHT + BUBBLE_POINTER_HEIGHT + BUBBLE_GAP - (SLIDER_HEIGHT - SLIDER_GROOVE_HEIGHT) // 2 + 1
)  # the last pixel is a margin, so that the smoothed edge of the bubble is not cut
