-- Exercises the provider contract without changing the running desktop.
local plugin = arg[1]
local fixture = {
  current = "original",
  profiles = {
    { id = "original", title = "Your original", description = "Original desktop" },
    { id = "glyph", title = "Glyph", description = "Dot matrix desktop", icon = "/profiles/glyph/nothing.svg" },
  },
}

local function host()
  local state = { pending = {}, rows = {}, commands = {}, notifications = {}, decoded = fixture, starts = true }
  local environment = setmetatable({
    launcher = {
      setResults = function(query, rows)
        state.query = query
        state.rows = rows
      end,
    },
    noctalia = {
      json = { decode = function(_) return state.decoded end },
      string = { trim = function(value) return value:match("^%s*(.-)%s*$") end },
      fuzzyScore = function(pattern, text)
        return text:lower():find(pattern:lower(), 1, true) and 10 or nil
      end,
      runAsync = function(argv, callback)
        assert(type(argv) == "table", "Subprocess arguments must bypass shell parsing")
        table.insert(state.commands, argv)
        if callback then table.insert(state.pending, callback) end
        return state.starts
      end,
      notifyError = function(title, message) table.insert(state.notifications, { title, message }) end,
    },
  }, { __index = _G })
  assert(loadfile(plugin, "t", environment))()
  state.api = environment
  return state
end

local function complete(state, index)
  state.pending[index]({ exitCode = 0, stdout = "fixture", stderr = "" })
end

local state = host()
state.api.onQuery("")
assert(state.rows[1].id == "loading")
complete(state, 1)
assert(#state.rows == 2 and state.rows[1].id == "original")
assert(state.rows[1].subtitle:find("Active profile", 1, true))
assert(state.rows[1].glyph == "circle-check" and state.rows[1].icon == nil)
assert(state.rows[2].icon == fixture.profiles[2].icon, "Glyph must retain its Nothing mark")
state.api.onActivate("glyph")
local command = state.commands[#state.commands]
assert(command[1] == "desktop-theme" and command[2] == "switch" and command[3] == "glyph")
local count = #state.commands
state.api.onActivate("glyph; touch /tmp/injected")
assert(#state.commands == count, "Unknown result IDs must not execute commands")

state = host()
state.api.onQuery("glyph")
complete(state, 1)
assert(#state.rows == 1 and state.rows[1].id == "glyph")
assert(state.rows[1].icon == fixture.profiles[2].icon)

state = host()
state.decoded = { current = "glyph", profiles = fixture.profiles }
state.api.onQuery("")
complete(state, 1)
assert(state.rows[2].icon == fixture.profiles[2].icon)
assert(state.rows[2].subtitle:find("Active profile", 1, true), "Branding must preserve active status")

state = host()
state.api.onQuery("glyph")
state.api.onQuery("original")
complete(state, 2)
complete(state, 1)
assert(state.query == "original" and state.rows[1].id == "original", "Late queries must not replace active results")
state.api.onActivate("original")
assert(state.commands[#state.commands][3] == "original")

state = host()
state.api.onQuery("")
state.pending[1]({ exitCode = 1, stdout = "", stderr = "helper failed" })
assert(state.rows[1].id == "error" and state.rows[1].subtitle == "helper failed")
count = #state.commands
state.api.onActivate("error")
assert(#state.commands == count)

state = host()
state.decoded = { current = "original", profiles = { "malformed profile" } }
state.api.onQuery("")
complete(state, 1)
assert(state.rows[1].id == "error", "Malformed success must not look like an empty list")

state = host()
state.decoded = { current = "glyph", profiles = { { id = "glyph", title = "Glyph", description = "Desktop", icon = {} } } }
state.api.onQuery("")
complete(state, 1)
assert(state.rows[1].id == "error", "Malformed icons must be reported")

state = host()
state.starts = false
state.api.onQuery("")
assert(state.rows[1].id == "error")

print("Profile provider: listing, filtering, activation, query ordering and failures: PASS")
