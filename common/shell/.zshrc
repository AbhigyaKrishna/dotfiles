# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

source /usr/share/cachyos-zsh-config/cachyos-config.zsh

# Keep $path unique. The appends below run again on every re-source, and
# .profile and the cachyos config add entries of their own.
typeset -U path PATH

alias code='code-insiders'
alias ssh='kitty +kitten ssh'
alias fzf='fzf --style full --preview "fzf-preview.sh {}" --bind "focus:transform-header:file --brief {}"'
alias task='go-task'

# Also set in ~/.config/environment.d/, but that only reaches the systemd
# graphical session. Shells started outside it (TTY, ssh, nested tooling)
# need these here, or ssh falls back to a non-existent /usr/lib/ssh/ssh-askpass.
export SSH_ASKPASS=/usr/bin/ksshaskpass
export GIT_ASKPASS=/usr/bin/ksshaskpass
export SSH_ASKPASS_REQUIRE=prefer
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/emulator
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin

[[ "$TERM_PROGRAM" == "vscode" ]] && . "$(code --locate-shell-integration-path zsh)"

export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

unsetopt correct_all

source /usr/share/nvm/init-nvm.sh

# Per-directory environment from .envrc, opt-in per project via `direnv allow`.
command -v direnv >/dev/null && eval "$(direnv hook zsh)"

# Shell history with fuzzy search and stats. --disable-up-arrow keeps plain up
# for the last command; Ctrl-R opens atuin.
command -v atuin >/dev/null && eval "$(atuin init zsh --disable-up-arrow)"
