import os

# no screen in CI: Qt draws the windows in memory
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
