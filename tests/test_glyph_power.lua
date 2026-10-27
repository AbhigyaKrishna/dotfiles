-- Runs the real panel script against a host double; never executes power commands.
local directory = arg[1]
local fixture = {
  { action = "lock", shortcut = "1" },
  { action = "lock_and_suspend", shortcut = "2", countdown_seconds = 10 },
  {
    action = "command",
    label = "Hibernate",
    command = "systemctl hibernate",
    shortcut = "3",
    countdown_seconds = 10,
  },
  { action = "reboot", shortcut = "4", countdown_seconds = 10 },
  { action = "logout", shortcut = "5", countdown_seconds = 10 },
  { action = "shutdown", shortcut = "6", countdown_seconds = 10 },
  {
    action = "command",
    label = "Reboot to UEFI",
    command = "systemctl reboot --firmware-setup",
    shortcut = "7",
    countdown_seconds = 10,
  },
}

local function host()
  local state = {
    now = 0,
    actions = fixture,
    commands = {},
    reads = {},
    notifications = {},
    closes = 0,
    starts = true,
    files = {},
    values = {},
    watchers = {},
  }
  local environment
  environment = setmetatable({
    ui = setmetatable({}, {
      __index = function(_, kind)
        return function(props, children)
          return { kind = kind, props = props, children = children or {} }
        end
      end,
    }),
    require = function(path)
      return assert(loadfile(directory .. "/" .. path, "t", environment))()
    end,
    panel = {
      render = function(tree)
        state.tree = tree
      end,
      setWantsSecondTicks = function(_) end,
      close = function()
        state.closes = state.closes + 1
      end,
    },
    noctalia = {
      state = {
        set = function(key, value)
          state.values[key] = value
          if state.watchers[key] then
            state.watchers[key](value)
          end
        end,
        get = function(key)
          return state.values[key]
        end,
        watch = function(key, callback)
          state.watchers[key] = callback
        end,
      },
      layer = {
        show = function(id)
          assert(id == "screen")
          state.layerShown = true
        end,
        hide = function(id)
          assert(id == "screen")
          state.layerShown = false
        end,
      },
      getSetting = function(path)
        assert(path == "shell.session.actions")
        return state.actions
      end,
      outputs = function()
        return { { name = "screen", width = 1920, height = 1080 } }
      end,
      focusedOutputName = function()
        return "screen"
      end,
      nowMs = function()
        return state.now
      end,
      pluginDataDir = function()
        return "/virtual/glyph-power"
      end,
      writeFile = function(path, contents)
        state.files[path] = contents
        return true
      end,
      log = function(message)
        error(message)
      end,
      readFileAsync = function(path, callback)
        table.insert(state.reads, callback)
        return true
      end,
      runAsync = function(command, callback)
        table.insert(state.commands, { command = command, complete = callback })
        return state.starts
      end,
      json = {
        decode = function(_)
          return { {}, {}, {} }
        end,
      },
      notifyError = function(title, message)
        table.insert(state.notifications, { title, message })
      end,
    },
  }, { __index = _G })
  assert(loadfile(directory .. "/menu.luau", "t", environment))()
  state.api = environment
  state.api.onOpen()
  return state
end

local function key(state, chord)
  state.api.onKey(chord, true)
end

local function frame(state, milliseconds)
  state.now = state.now + milliseconds
  state.api.onFrameTick(tostring(milliseconds))
end
local function powerCommands(state)
  local commands = {}
  for _, request in ipairs(state.commands) do
    if type(request.command) == "string" or request.command[1] ~= "niri" then
      table.insert(commands, request)
    end
  end
  return commands
end

local state = host()
assert(state.layerShown, "Opening the keyboard controller must show the full-screen layer")
assert(#powerCommands(state) == 0, "Opening the menu must not execute an action")
key(state, "Return")
state.now = 9000
state.api.update()
assert(#powerCommands(state) == 0, "Countdown must run for the full configured duration")
state.now = 10000
state.api.update()
local request = powerCommands(state)[1]
assert(table.concat(request.command, " ") == "noctalia msg session shutdown")
key(state, "Return")
state.api.update()
assert(#powerCommands(state) == 1, "Pending execution must not launch twice")
request.complete({ exitCode = 0, stdout = "ok", stderr = "" })
assert(state.closes == 1)

state = host()
key(state, "Return")
key(state, "Up")
state.now = 20000
state.api.update()
assert(#powerCommands(state) == 0, "Changing selection must cancel the countdown")
key(state, "3")
key(state, "Return")
assert(
  powerCommands(state)[1].command == "systemctl hibernate",
  "Custom commands must retain Original's definition"
)

state = host()
key(state, "Return")
state.api.onClose()
assert(not state.layerShown, "Closing must remove the layer and its input surface")
state.now = 20000
state.api.update()
assert(#powerCommands(state) == 0, "Closing with Escape must cancel pending actions")

state = host()
key(state, "1")
assert(
  table.concat(powerCommands(state)[1].command, " ") == "noctalia msg session lock",
  "Immediate actions must remain immediate"
)

state = host()
key(state, "7")
key(state, "Return")
request = powerCommands(state)[1]
assert(request.command == "systemctl reboot --firmware-setup")
request.complete({ exitCode = 1, stdout = "", stderr = "firmware unavailable" })
assert(state.notifications[1][2] == "firmware unavailable")
assert(state.closes == 0, "A failed action must keep the menu open")

state = host()
state.starts = false
key(state, "1")
assert(#state.notifications == 1, "Failure to start an action must be visible")

state = host()
state.actions = { fixture[1], { action = "shutdown", shortcut = "6", enabled = false } }
state.api.onOpen()
key(state, "6")
assert(#powerCommands(state) == 0, "Disabled actions must not be reachable by shortcut")

state = host()
local oldRead = state.reads[1]
state.api.onClose()
state.api.onOpen()
local currentView = state.values.power_view
oldRead("9999.9 0")
assert(state.values.power_view == currentView, "Late metric reads must not mutate a reopened panel")
state.reads[#state.reads]("175000.00 0")
local foundUptime = false
for _, svg in pairs(state.files) do
  if svg:find("48:36", 1, true) then
    foundUptime = true
  end
end
assert(foundUptime, "The uptime ring must display real hours and minutes")

local function findNode(tree, key)
  if tree.props.key == key then
    return tree
  end
  for _, child in ipairs(tree.children) do
    local found = findNode(child, key)
    if found then
      return found
    end
  end
end

state = host()
state.api.layer = {
  render = function(tree)
    state.overlay = tree
  end,
  setNeedsFrameTick = function(enabled)
    state.frameTicks = enabled
  end,
}
assert(loadfile(directory .. "/screen.luau", "t", state.api))()
assert(state.overlay.props.fill == "#000000c7", "The visual layer must leave the backdrop translucent")
for step = 1, #fixture do
  local rows = findNode(state.overlay, "action-list").children
  assert(#rows == #fixture, "All imported actions must remain visible")
  for index, row in ipairs(rows) do
    assert(row.props.key == "action-" .. index, "Changing selection must not rotate the action list")
    local selected = index == state.values.power_view.selected
    assert(
      row.props.height == (selected and 180 or 62),
      "Only the selected row should reserve expanded space"
    )
    assert(row.children[1].props.opacity == (selected and 1 or 0))
  end
  key(state, "Up")
  assert(state.frameTicks, "Selection changes must request animation frames")
  frame(state, 240)
  assert(not state.frameTicks, "Animation frames must stop when the transition finishes")
end

local oldSelected = state.values.power_view.selected
key(state, "Up")
local newSelected = state.values.power_view.selected
assert(
  findNode(state.overlay, "action-" .. oldSelected).props.height == 180,
  "Retargeting must not jump on the first frame"
)
assert(findNode(state.overlay, "action-" .. newSelected).props.height == 62)
state.api.onFrameTick("5000")
assert(
  findNode(state.overlay, "action-" .. newSelected).props.height == 62,
  "An idle-inclusive first-frame delta must not skip the animation"
)
frame(state, 60)
local shrinking = findNode(state.overlay, "action-" .. oldSelected)
local growing = findNode(state.overlay, "action-" .. newSelected)
assert(shrinking.props.height > 62 and shrinking.props.height < 180)
assert(growing.props.height > 62 and growing.props.height < 180)
assert(growing.children[2].props.fontSize > 46 and growing.children[2].props.fontSize < 160)
local beforeRetarget = growing.props.height
key(state, "Up")
assert(
  findNode(state.overlay, "action-" .. newSelected).props.height == beforeRetarget,
  "Rapid navigation must continue from the current geometry"
)
frame(state, 120)
local totalHeight = 0
for _, row in ipairs(findNode(state.overlay, "action-list").children) do
  totalHeight = totalHeight + row.props.height
end
assert(
  math.abs(totalHeight - (180 + (#fixture - 1) * 62)) < 0.001,
  "Expansion and contraction must preserve total list height"
)
frame(state, 120)
assert(not state.frameTicks)
assert(state.overlay.props.opacity == 1, "The full-redraw workaround must return to full opacity at rest")

local hoverRow = findNode(state.overlay, "action-3")
assert(hoverRow.props.onHover == "onActionHover", "Rows must expose a stable hover handler while animating")
state.api.onActionHover("true", hoverRow.props.key)
assert(state.values.power_view.selected == 3, "Hover must highlight its option")
assert(state.frameTicks, "Hover selection must use the easing animation")
assert(#powerCommands(state) == 0, "Hover must never confirm an action")
frame(state, 60)
local hoverHeight = findNode(state.overlay, "action-3").props.height
assert(hoverHeight > 62 and hoverHeight < 180, "Hovered options must expand smoothly")
state.api.onActionHover("false", hoverRow.props.key)
assert(state.values.power_view.selected == 3, "Pointer leave must retain the last selection")
frame(state, 180)

key(state, "7")
state.api.onActionHover("true", "action-1")
assert(state.values.power_view.selected == 1)
assert(#powerCommands(state) == 0, "Hovering Lock must not run its immediate action")
state.now = state.now + 20000
state.api.update()
assert(#powerCommands(state) == 0, "Hovering another option must cancel a pending countdown")

local clicked = findNode(state.overlay, "action-3")
assert(clicked, "Layer must render imported actions as click targets")
clicked.props.onClick()
assert(#powerCommands(state) == 0, "Clicking Hibernate must arm its countdown")
key(state, "Return")
assert(
  powerCommands(state)[1].command == "systemctl hibernate",
  "Layer clicks must reach the keyboard controller"
)
state.api.onClose()
state.api.onOpen()
clicked.props.onClick()
assert(#powerCommands(state) == 1, "Callbacks from an old layer must not activate a reopened menu")

key(state, "7")
local event = state.values.power_action
state.api.onActionHover("true", "action-7")
assert(
  state.values.power_action == event,
  "Repeated hover on the selected option must not rearm or confirm it"
)
state.now = state.now + 10000
state.api.update()
assert(#powerCommands(state) == 2, "Repeated hover must preserve the current countdown")

print("Glyph power: hover easing, countdown, cancellation, shortcuts, commands, failures and lifecycle: PASS")

local shortcutPanel = nil
local shortcutEnvironment = setmetatable({
  shortcut = { setLabel = function(_) end, setIcon = function(_) end },
  noctalia = {
    loadFont = function(_)
      return "Glyph UI"
    end,
    togglePanel = function(id)
      shortcutPanel = id
    end,
  },
}, { __index = _G })
assert(loadfile(directory .. "/shortcut.luau", "t", shortcutEnvironment))()
shortcutEnvironment.onClick()
assert(shortcutPanel == "dotfiles/glyph-power:menu", "Control Center Power must open the Glyph overlay")
print("Glyph Power Control Center shortcut: PASS")
