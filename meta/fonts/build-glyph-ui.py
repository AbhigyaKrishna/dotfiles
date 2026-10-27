"""Build Glyph's mixed UI family from its bundled fonts (requires fontTools)."""

from pathlib import Path

from fontTools.ttLib import TTFont

DIRECTORY = (
    Path(__file__).resolve().parents[2] / "common/appearance/.local/share/fonts/glyph"
)
FACES = (
    ("SpaceGrotesk-Regular.otf", "Regular", 400),
    ("SpaceGrotesk-Medium.otf", "Medium", 500),
    ("GlyphDots-Bold.ttf", "SemiBold", 600),
    ("GlyphDots-Bold.ttf", "Bold", 700),
)


def build_face(source, style, weight):
    font = TTFont(DIRECTORY / source, recalcTimestamp=False)
    full_name = f"Glyph UI {style}"
    postscript_name = f"GlyphUI-{style}"
    names = {
        1: "Glyph UI",
        2: style,
        3: f"{postscript_name}-1.0",
        4: full_name,
        6: postscript_name,
        16: "Glyph UI",
        17: style,
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
    font["OS/2"].usWeightClass = weight
    font["OS/2"].fsSelection &= ~((1 << 5) | (1 << 6))
    if weight == 400:
        font["OS/2"].fsSelection |= 1 << 6
    elif weight == 700:
        font["OS/2"].fsSelection |= 1 << 5
    font["head"].macStyle = (font["head"].macStyle & ~1) | int(weight == 700)
    if "CFF " in font:
        cff = font["CFF "].cff
        cff.fontNames[0] = postscript_name
        cff.topDictIndex[0].FullName = full_name
        cff.topDictIndex[0].FamilyName = "Glyph UI"
        cff.topDictIndex[0].Weight = style
    font.save(DIRECTORY / f"{postscript_name}{Path(source).suffix}")


for source, style, weight in FACES:
    build_face(source, style, weight)
