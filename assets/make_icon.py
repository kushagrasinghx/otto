"""Generate assets/icon.ico (the app / .exe icon) from icon.png.

Run:  python assets/make_icon.py

Writes a single 256x256 icon from icon.png. 256 is the standard "large" icon
size, so it's pixel-perfect in Start Menu / high-DPI views and downscales
cleanly to the small taskbar/desktop slots — unlike an odd size (e.g. 100px)
which Windows has to blur-scale everywhere. Design is unchanged.
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "icon.png"     # 512x512 source artwork
OUT = HERE / "icon.ico"

src = Image.open(SRC).convert("RGBA").resize((256, 256), Image.LANCZOS)
src.save(OUT, format="ICO", sizes=[(256, 256)])
print("wrote", OUT, "from", SRC.name, "-> 256x256")
