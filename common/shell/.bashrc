#
# ~/.bashrc
#

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

alias ls='ls --color=auto'
alias grep='grep --color=auto'
PS1='[\u@\h \W]\$ '

# Point the docker CLI at the rootless daemon, as .zshrc and config.fish do.
# Without this it falls back to /var/run/docker.sock — the rootful socket.
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
. "$HOME/.cargo/env"

source /usr/share/nvm/init-nvm.sh

# Per-directory environment from .envrc, opt-in per project via `direnv allow`.
command -v direnv >/dev/null && eval "$(direnv hook bash)"

# Shell history with fuzzy search and stats, as in .zshrc and config.fish.
command -v atuin >/dev/null && eval "$(atuin init bash --disable-up-arrow)"
