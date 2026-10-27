"""Build the rounded Doto instance used by Noctalia (requires fontTools)."""

from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

directory = (
    Path(__file__).resolve().parents[2] / "common/appearance/.local/share/fonts/glyph"
)
font = TTFont(directory / "Doto[ROND,wght].ttf", recalcTimestamp=False)
instantiateVariableFont(font, {"ROND": 100, "wght": 700}, inplace=True)
# A distinct family avoids depending on variable-axis support in shell renderers.
names = {
    1: "Glyph Dots",
    2: "Bold",
    3: "GlyphDots-Bold-1.0",
    4: "Glyph Dots Bold",
    6: "GlyphDots-Bold",
    16: "Glyph Dots",
    17: "Bold",
}
for record in list(font["name"].names):
    if record.nameID in names:
        font["name"].setName(
            names[record.nameID],
            record.nameID,
            record.platformID,
            record.platEncID,
            record.langID,
        )
font.save(directory / "GlyphDots-Bold.ttf")
