"""
Start the GUI with `python -m apkit4d.gui [file.czi]` until the CLI has a `gui` command.
"""

import sys
from pathlib import Path

from apkit4d.gui.app import run

sys.exit(run(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
