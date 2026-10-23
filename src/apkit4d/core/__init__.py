"""
Core logic and schemas for apkit4d
This does not includes any visualization or compelx code just a simple point
tht can be easily refactored into something else to start
Why do we have the schemas here and not the separate modules?
- Multiple part of the code migh need them so having all of them in a common place migth be good
    But again this can be easily changed
"""

from apkit4d.core.models import TrackingConfig

# This may be dangerous but I wanted to try how it works
# basically python has garbage support for proper classes but has this shit for wildcards import from modules
# since this had tro be a bad joke I decided to try it.
# If we forgot it exists it WILL cause problems
__all__ = ["TrackingConfig"]
