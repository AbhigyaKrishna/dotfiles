local ring = {}

function ring.svg(value, windows, remaining)
  local parts = { '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 480">' }
  for index = 0, 59 do
    local angle = index * math.pi / 30 - math.pi / 2
    local x = 240 + math.cos(angle) * 222
    local y = 240 + math.sin(angle) * 222
    local color = remaining and "#d71921" or "#f2f2f2"
    table.insert(parts, string.format('<circle cx="%.2f" cy="%.2f" r="4" fill="%s"/>', x, y, color))
  end
  local heading = remaining and "CONFIRMING IN" or "UPTIME"
  local footer = remaining and "ENTER AGAIN TO RUN NOW"
    or (windows and (windows .. " WINDOWS OPEN") or "WINDOW COUNT UNAVAILABLE")
  table.insert(
    parts,
    '<g text-anchor="middle" fill="#8c8c8c" font-family="Space Mono" font-size="12" letter-spacing="2">'
  )
  table.insert(parts, '<text x="240" y="181">' .. heading .. "</text>")
  table.insert(parts, '<text x="240" y="306">' .. footer .. "</text></g>")
  table.insert(
    parts,
    '<text x="240" y="270" text-anchor="middle" fill="#f2f2f2" font-family="Glyph Dots" font-size="82">'
      .. value
      .. "</text></svg>"
  )
  return table.concat(parts)
end

return ring
