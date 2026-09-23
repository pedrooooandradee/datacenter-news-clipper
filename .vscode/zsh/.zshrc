# Terminal do Cursor neste projeto: carrega o ~/.zshrc normal e depois ativa o venv do projeto.
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc"
_clipping_root="${${(%):-%x}:A:h:h:h}"
[ -f "$_clipping_root/venv/bin/activate" ] && source "$_clipping_root/venv/bin/activate"
unset _clipping_root
