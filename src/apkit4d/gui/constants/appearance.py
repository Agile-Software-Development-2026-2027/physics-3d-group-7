"""
Sizes of the window and of its parts, in pixels, and opacity of the splitter handles.

Only sizes that belong to one component are here. The sizes shared by every component are in
`theme.tokens`.
"""

# window
WINDOW_WIDTH: int = 1200
WINDOW_HEIGHT: int = 800

# columns, from left to right: left panel, center panel, right panel
SIDE_PANEL_WIDTH: int = 200  # initial width of the side columns, when their controls fit in it
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

# playback bar: the reference look of the application. The sizes that every component shares
# (radius, control height, icons, spacing, fonts, color mixes) are in `theme.tokens`
BAR_MARGINS: tuple[int, int, int, int] = (18, 0, 18, 14)  # left, top, right, bottom
TRANSPORT_BUTTON_SIZE: int = 36
PLAY_BUTTON_SIZE: int = 44
TRANSPORT_ICON_SIZE: int = 20
PLAY_ICON_SIZE: int = 22
COUNTER_SPACING: int = 10  # extra space between the buttons and the counter
COUNTER_VERTICAL_PADDING: int = 6
SPEED_STEPPER_WIDTH: int = 148
STEP_STEPPER_WIDTH: int = 98
STEPPER_BUTTON_SIZE: int = 26  # the - and + buttons inside a number field
DIVIDER_HEIGHT: int = 24

# slider of the frames
SLIDER_HEIGHT: int = 22
SLIDER_PADDING: int = 9  # space between the ends of the groove and the sides of the widget
SLIDER_GROOVE_HEIGHT: int = 6
SLIDER_HANDLE_RADIUS: float = 7.2
SLIDER_HANDLE_RING: float = 2.6

# preview that follows the mouse on the slider: a marker on the groove and a bubble above it
HOVER_MARKER_WIDTH: int = 2
HOVER_MARKER_HALF_HEIGHT: int = 8
HOVER_MARKER_OPACITY: int = 230  # from 0 (invisible) to 255 (solid)
BUBBLE_HEIGHT: int = 24  # of the body of the bubble, without the pointer
BUBBLE_POINTER_HEIGHT: int = 6
BUBBLE_POINTER_WIDTH: int = 10
BUBBLE_GAP: int = 3  # between the tip of the pointer and the groove
BUBBLE_PADDING: int = 11  # on the left and on the right of the text
# the slider keeps some room above its groove, where the bubble of the preview is drawn
SLIDER_HEADROOM: int = (
    BUBBLE_HEIGHT + BUBBLE_POINTER_HEIGHT + BUBBLE_GAP - (SLIDER_HEIGHT - SLIDER_GROOVE_HEIGHT) // 2 + 1
)  # the last pixel is a margin, so that the smoothed edge of the bubble is not cut

HISTOGRAM_HEIGHT_RANGE: tuple[int, int] = (200, 250)
