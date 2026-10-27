local sequence = 0
local transitionDurationMs = 240
local currentView = nil
local weights = {}
local initialWeights = {}
local transitionStartedMs = 0
local animating = false
local animationFrame = 0

local function sendAction(view, kind, index)
  sequence = sequence + 1
  noctalia.state.set("power_action", {
    generation = view.generation,
    index = index,
    kind = kind,
    sequence = sequence,
  })
end

local function actionRow(view, index)
  local text = view.actions[index].title
  local weight = weights[index] or 0
  local fontSize = 46 + (math.min(160, 1500 / #text) - 46) * weight
  local shade = math.floor(104 + 138 * weight + 0.5)
  local scale = view.scale
  return ui.row({
    key = "action-" .. index,
    height = (62 + 118 * weight) * scale,
    gap = 22 * scale,
    align = "center",
    onHover = "onActionHover",
    onClick = function()
      sendAction(view, "activate", index)
    end,
  }, {
    ui.box({
      width = 15 * scale,
      height = 15 * scale,
      radius = 8 * scale,
      fill = "#d71921",
      opacity = weight,
    }),
    ui.label({
      text = text,
      fontFamily = "Glyph Dots",
      fontSize = fontSize * scale,
      color = string.format("#%02x%02x%02x", shade, shade, shade),
      baseline = "inkCentered",
      maxLines = 1,
    }),
  })
end

local function render(view)
  if not view then
    return
  end
  local scale = view.scale
  local rows = {}
  for index = 1, #view.actions do
    table.insert(rows, actionRow(view, index))
  end
  if #rows == 0 then
    table.insert(rows, ui.label({ text = "NO POWER ACTIONS ENABLED", color = "#f2f2f2" }))
  end
  local metric = view.ringPath
      and ui.image({ path = view.ringPath, width = 430 * scale, height = 430 * scale })
    or ui.label({ text = "UPTIME UNAVAILABLE", color = "#8c8c8c" })
  layer.render(ui.column({
    flexGrow = 1,
    fill = "#000000c7",
    -- Noctalia's partial damage can omit unchanged siblings while rows resize.
    -- A sub-perceptual group-opacity change invalidates the complete surface.
    opacity = animating and (0.9998 + 0.0001 * (animationFrame % 2)) or 1,
  }, {
    ui.column({
      flexGrow = 1,
      paddingH = 150 * scale,
      paddingV = 64 * scale,
    }, {
      ui.spacer({ flexGrow = 1 }),
      ui.row({ align = "center", gap = 60 * scale }, {
        ui.column({ key = "action-list", flexGrow = 1, gap = 4 * scale }, rows),
        metric,
      }),
      ui.spacer({ flexGrow = 1 }),
      ui.row({
        height = 28 * scale,
        onClick = function()
          sendAction(view, "close")
        end,
      }, {
        ui.label({
          text = view.executing and "RUNNING POWER ACTION…"
            or "↑↓ SELECT     ↵ CONFIRM     ESC CANCEL     1–7 SHORTCUTS",
          fontFamily = "Space Mono",
          fontSize = 12 * scale,
          color = "#8c8c8c",
        }),
      }),
    }),
  }))
end

function onActionHover(entered, key)
  if entered ~= "true" or currentView == nil then
    return
  end
  local index = tonumber(string.match(key, "^action%-(%d+)$"))
  if index == nil or currentView.actions[index] == nil or currentView.selected == index then
    return
  end
  sendAction(currentView, "select", index)
end

local function receiveView(view)
  if not view then
    return
  end
  local reset = currentView == nil
    or currentView.generation ~= view.generation
    or #currentView.actions ~= #view.actions
  if reset then
    weights = {}
    for index = 1, #view.actions do
      weights[index] = index == view.selected and 1 or 0
    end
    animating = false
    layer.setNeedsFrameTick(false)
  elseif currentView.selected ~= view.selected then
    initialWeights = {}
    for index, weight in ipairs(weights) do
      initialWeights[index] = weight
    end
    transitionStartedMs = noctalia.nowMs()
    animating = true
    layer.setNeedsFrameTick(true)
  end
  currentView = view
  render(view)
end

function onFrameTick()
  if not animating then
    return
  end
  -- The first frame after resting may include the entire idle interval in its
  -- delta. Measure from the selection change so that frame cannot skip the ease.
  local elapsedMs = math.max(0, noctalia.nowMs() - transitionStartedMs)
  animationFrame = animationFrame + 1
  local progress = math.min(1, elapsedMs / transitionDurationMs)
  local eased = progress * progress * (3 - 2 * progress)
  for index, initial in ipairs(initialWeights) do
    local target = index == currentView.selected and 1 or 0
    weights[index] = initial + (target - initial) * eased
  end
  if progress == 1 then
    animating = false
    layer.setNeedsFrameTick(false)
  end
  render(currentView)
end

noctalia.state.watch("power_view", receiveView)
receiveView(noctalia.state.get("power_view"))
