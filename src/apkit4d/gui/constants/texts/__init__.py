"""
Every text shown to the user, one module for each area of the window.

Texts with `{...}` are templates: fill them with `str.format`.

Each module holds the texts of one area of the window; this package re-exports all of them,
so use them as `texts.BUTTON_PLAY`.
"""

from apkit4d.gui.constants.texts.batch import *  # noqa: F403
from apkit4d.gui.constants.texts.detection import *  # noqa: F403
from apkit4d.gui.constants.texts.histograms import *  # noqa: F403
from apkit4d.gui.constants.texts.left_panel import *  # noqa: F403
from apkit4d.gui.constants.texts.main_window import *  # noqa: F403
from apkit4d.gui.constants.texts.playback import *  # noqa: F403
from apkit4d.gui.constants.texts.preprocessing import *  # noqa: F403
from apkit4d.gui.constants.texts.right_panel import *  # noqa: F403
from apkit4d.gui.constants.texts.roi import *  # noqa: F403
from apkit4d.gui.constants.texts.tracking import *  # noqa: F403
