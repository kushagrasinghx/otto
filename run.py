"""Launch Otto.

Usage:
    python run.py
"""

import os

# Silence a harmless Qt console warning. On Windows, python.exe's own bundled
# manifest typically locks in PER_MONITOR_AWARE_V2 DPI awareness before Qt
# gets a chance to request it itself, so Qt's own (redundant) attempt fails
# with "Access is denied" — the effective DPI awareness is already correct
# either way (the message confirms it), this just hides the noisy log line.
# Must be set before any PySide6 import, hence before `from src.main import`.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")

from src.main import main

if __name__ == "__main__":
    main()
