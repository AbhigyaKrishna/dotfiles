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
