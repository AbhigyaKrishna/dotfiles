local ring = require("./ring.luau")
local actions = {}
local selected = 1
local deadline = nil
local isOpen = false
local executing = false
local generation = 0
local uptime = nil
local windowCount = nil
local ringRevision = 0
local ringPath = nil
local scale = 1
local ticks = 0
local render

local labels = {
  lock = "LOCK",
  lock_and_suspend = "SLEEP",
  suspend = "SLEEP",
  reboot = "REBOOT",
  logout = "LOG OUT",
  shutdown = "SHUT DOWN",
}

local function title(entry)
  if entry.label and entry.label ~= "" then
    return string.upper(entry.label)
  end
  return labels[entry.action] or string.upper(entry.action)
end

local function remainingSeconds()
  if deadline == nil then
    return nil
  end
  return math.max(0, math.ceil((deadline - noctalia.nowMs()) / 1000))
end

local function selectAction(index)
  if executing or index < 1 or index > #actions or selected == index then
    return
  end
  selected = index
  deadline = nil
  render()
end

local function executeAction()
  local entry = actions[selected]
  if not entry or executing then
    return
  end
  executing = true
  deadline = nil
  local command = { "noctalia", "msg", "session", entry.action }
  if entry.command and entry.command ~= "" then
    command = entry.command
  end
  local version = generation
  local accepted = noctalia.runAsync(command, function(response)
    if generation ~= version then
      return
    end
    if response.exitCode == 0 then
      panel.close()
    else
      executing = false
      noctalia.notifyError(
        "Power action failed",
        response.stderr ~= "" and response.stderr or response.stdout
      )
      if isOpen then
        render()
      end
    end
  end)
  if not accepted then
    executing = false
    noctalia.notifyError("Power action failed", "Could not start " .. title(entry))
  end
  render()
end

local function activate()
  local entry = actions[selected]
  if not entry or executing then
    return
  end
  local seconds = entry.countdown_seconds or 0
  if deadline ~= nil or seconds <= 0 then
    executeAction()
    return
  end
  deadline = noctalia.nowMs() + seconds * 1000
  render()
end

local function renderRing()
  local remaining = remainingSeconds()
  local value = "--:--"
  if uptime ~= nil then
    value = string.format("%02d:%02d", math.floor(uptime / 3600), math.floor(uptime / 60) % 60)
  end
  if remaining ~= nil then
    value = string.format("%02d", remaining)
  end
  local directory, reason = noctalia.pluginDataDir()
  if not directory then
    noctalia.log("Cannot create uptime image: " .. tostring(reason))
    return
  end
  -- Alternating two filenames invalidates the image cache without accumulating files.
  ringRevision = (ringRevision + 1) % 2
  local path = directory .. "/uptime-" .. ringRevision .. ".svg"
  local written, error = noctalia.writeFile(path, ring.svg(value, windowCount, remaining))
  if written then
    ringPath = path
  else
    ringPath = nil
    noctalia.log("Cannot write uptime image: " .. tostring(error))
  end
end

render = function()
  if not isOpen then
    return
  end
  renderRing()
  local entries = {}
  for index, entry in ipairs(actions) do
    entries[index] = { title = title(entry) }
  end
  noctalia.state.set("power_view", {
    generation = generation,
    selected = selected,
    actions = entries,
    ringPath = ringPath,
    scale = scale,
    executing = executing,
  })
end

local function refreshMetrics()
  local version = generation
  local reading = noctalia.readFileAsync("/proc/uptime", function(contents)
    if not isOpen or generation ~= version then
      return
    end
    uptime = contents and tonumber(string.match(contents, "^([%d.]+)")) or nil
    render()
  end)
  if not reading then
    uptime = nil
  end
  if ticks % 5 ~= 0 then
    return
  end
  local querying = noctalia.runAsync({ "niri", "msg", "--json", "windows" }, function(response)
    if not isOpen or generation ~= version then
      return
    end
    local windows = response.exitCode == 0 and noctalia.json.decode(response.stdout) or nil
    windowCount = type(windows) == "table" and #windows or nil
    render()
  end)
  if not querying then
    windowCount = nil
  end
end

function onOpen()
  generation = generation + 1
  isOpen = true
  executing = false
  deadline = nil
  uptime = nil
  windowCount = nil
  ticks = 0
  actions = {}
  selected = 1
  for _, entry in ipairs(noctalia.getSetting("shell.session.actions") or {}) do
    if entry.enabled ~= false then
      table.insert(actions, entry)
      if entry.action == "shutdown" then
        selected = #actions
      end
    end
  end
  scale = 1
  for _, output in ipairs(noctalia.outputs()) do
    if output.name == noctalia.focusedOutputName() then
      scale = math.min(output.width / 1920, output.height / 1080, 1.3)
      break
    end
  end
  panel.setWantsSecondTicks(true)
  panel.render(ui.box({ width = 1, height = 1, fill = "#00000000" }))
  render()
  noctalia.layer.show("screen")
  refreshMetrics()
end

function onClose()
  isOpen = false
  deadline = nil
  generation = generation + 1
  noctalia.layer.hide("screen")
end

noctalia.state.watch("power_action", function(event)
  if not isOpen or event.generation ~= generation then
    return
  end
  if event.kind == "close" then
    panel.close()
    return
  end
  if event.kind ~= "select" and event.kind ~= "activate" then
    return
  end
  if executing or type(event.index) ~= "number" or actions[event.index] == nil then
    return
  end
  selectAction(event.index)
  if event.kind == "activate" then
    activate()
  end
end)

function onKey(chord, pressed)
  if not pressed or not isOpen or executing or #actions == 0 then
    return
  end
  if chord == "Up" or chord == "k" then
    selectAction((selected - 2) % #actions + 1)
  elseif chord == "Down" or chord == "j" then
    selectAction(selected % #actions + 1)
  elseif chord == "Return" or chord == "KP_Enter" or chord == "space" then
    activate()
  elseif tonumber(chord) then
    for index, entry in ipairs(actions) do
      if entry.shortcut == chord then
        selectAction(index)
        activate()
        break
      end
    end
  end
end

function update()
  if not isOpen then
    return
  end
  if deadline ~= nil and remainingSeconds() == 0 then
    executeAction()
    return
  end
  ticks = ticks + 1
  refreshMetrics()
  render()
end
