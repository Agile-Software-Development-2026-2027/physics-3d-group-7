"""
General facts about the application.
"""

from pathlib import Path

from platformdirs import user_documents_path

APP_NAME: str = "ApKit4D"
CZI_SUFFIX: str = ".czi"  # the only file format the application opens
QT_STYLE: str = "Fusion"  # looks the same on every operating system and follows the palette

DEFAULT_PROCESSED_DATA_DIR: Path = user_documents_path() / "Apkit4d"
