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

# SSH_ASKPASS, GIT_ASKPASS and SSH_ASKPASS_REQUIRE come from
# ~/.config/environment.d/, which the graphical session already applies.
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
