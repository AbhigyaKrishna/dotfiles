-- Register the mixed family with the running Pango font map as well as Fontconfig.
for _, face in ipairs({
  "GlyphUI-Regular.otf",
  "GlyphUI-Medium.otf",
  "GlyphUI-SemiBold.ttf",
  "GlyphUI-Bold.ttf",
}) do
  local family, reason = noctalia.loadFont("~/.local/share/fonts/glyph/" .. face)
  if not family then
    noctalia.log("Cannot load Glyph UI font: " .. tostring(reason))
  end
end

shortcut.setLabel("Power")
shortcut.setIcon("power")

function onClick()
  noctalia.togglePanel("dotfiles/glyph-power:menu")
end
