function fzf --description 'alias fzf=fzf --style full --preview "fzf-preview.sh {}" --bind "focus:transform-header:file --brief {}"'
    command fzf --style full --preview "fzf-preview.sh {}" --bind "focus:transform-header:file --brief {}" $argv
end
