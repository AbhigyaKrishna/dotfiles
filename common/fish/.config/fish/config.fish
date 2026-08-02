source /usr/share/cachyos-fish-config/cachyos-config.fish

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end

zoxide init fish | source

# Per-directory environment from .envrc, opt-in per project via `direnv allow`.
command -q direnv; and direnv hook fish | source

# Shell history with fuzzy search and stats. --disable-up-arrow keeps plain up
# for the last command; Ctrl-R opens atuin.
command -q atuin; and atuin init fish --disable-up-arrow | source

# bun
set --export BUN_INSTALL "$HOME/.bun"
# Guarded: config.fish runs for every shell, so an unconditional prepend adds
# another copy at each nesting level.
if not contains $BUN_INSTALL/bin $PATH
    set --export PATH $BUN_INSTALL/bin $PATH
end

# Set per-session so it follows the runtime dir, rather than as a universal
# variable with a hardcoded uid baked in.
set --export DOCKER_HOST "unix://$XDG_RUNTIME_DIR/docker.sock"
