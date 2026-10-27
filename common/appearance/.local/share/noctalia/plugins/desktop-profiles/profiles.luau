local available = {}
local queryVersion = 0

local function unavailable(query, message)
  available = {}
  launcher.setResults(query, {
    { id = "error", title = "Profiles unavailable", subtitle = message, glyph = "alert-triangle" },
  })
end

local function showProfiles(query, response)
  local decoded = noctalia.json.decode(response.stdout)
  if type(decoded) ~= "table" or type(decoded.current) ~= "string" or type(decoded.profiles) ~= "table" then
    unavailable(query, "The profile helper returned an invalid response.")
    return
  end
  local rows = {}
  available = {}
  for _, profile in ipairs(decoded.profiles) do
    if type(profile) ~= "table" or type(profile.id) ~= "string" or type(profile.title) ~= "string" or type(profile.description) ~= "string" or (profile.icon ~= nil and type(profile.icon) ~= "string") then
      unavailable(query, "The profile helper returned an invalid profile.")
      return
    end
    local score = 0
    if query ~= "" then
      score = noctalia.fuzzyScore(query, profile.title .. " " .. profile.id .. " " .. profile.description)
    end
    if score ~= nil then
      local active = profile.id == decoded.current
      table.insert(rows, {
        id = profile.id,
        title = profile.title,
        subtitle = (active and "Active profile · " or "Switch profile · ") .. profile.description,
        glyph = active and "circle-check" or "palette",
        icon = profile.icon,
        score = score + (active and 1000 or 0),
      })
      available[profile.id] = true
    end
  end
  launcher.setResults(query, rows)
end

function onQuery(query)
  queryVersion = queryVersion + 1
  local version = queryVersion
  available = {}
  launcher.setResults(query, { { id = "loading", title = "Loading profiles…", glyph = "loader" } })
  local started = noctalia.runAsync({ "desktop-theme", "list" }, function(response)
    if version ~= queryVersion then
      return
    end
    if response.exitCode ~= 0 then
      unavailable(query, noctalia.string.trim(response.stderr))
      return
    end
    showProfiles(query, response)
  end)
  if not started then
    unavailable(query, "Could not start the desktop profile helper.")
  end
end

function onActivate(id)
  if not available[id] then
    return
  end
  -- Switching reloads this launcher and may replace its VM. The helper must
  -- outlive the entry and reports completion/errors through shell notifications.
  if not noctalia.runAsync({ "desktop-theme", "switch", id }) then
    noctalia.notifyError("Desktop Profiles", "Could not start the profile switch.")
  end
end
