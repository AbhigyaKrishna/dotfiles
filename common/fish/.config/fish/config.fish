source /usr/share/cachyos-fish-config/cachyos-config.fish

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end

zoxide init fish | source

# bun
set --export BUN_INSTALL "$HOME/.bun"
set --export PATH $BUN_INSTALL/bin $PATH

# Set per-session so it follows the runtime dir, rather than as a universal
# variable with a hardcoded uid baked in.
set --export DOCKER_HOST "unix://$XDG_RUNTIME_DIR/docker.sock"
