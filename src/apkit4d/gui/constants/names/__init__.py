"""
Object names of the components, one module for each area of the window.

The tests find the components with `findChild(type, name)`, so every component that a test needs
has a name here. Some names are also used as selectors in the stylesheets.

Each module holds the names of one area of the window; this package re-exports all of them,
so use them as `names.ROI_INSPECTOR_X_MIN`.
"""

from apkit4d.gui.constants.names.detection import *  # noqa: F403
from apkit4d.gui.constants.names.histograms import *  # noqa: F403
from apkit4d.gui.constants.names.left_panel import *  # noqa: F403
from apkit4d.gui.constants.names.main_window import *  # noqa: F403
from apkit4d.gui.constants.names.playback import *  # noqa: F403
from apkit4d.gui.constants.names.preprocessing import *  # noqa: F403
from apkit4d.gui.constants.names.right_panel import *  # noqa: F403
from apkit4d.gui.constants.names.roi import *  # noqa: F403
from apkit4d.gui.constants.names.tracking import *  # noqa: F403
from apkit4d.gui.constants.names.video_export import *  # noqa: F403
from apkit4d.gui.constants.names.widgets import *  # noqa: F403
