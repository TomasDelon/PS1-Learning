#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f PS1.Rproj && -f v21/coach.py && -f PUBLIC_MANIFEST.sha256 ]]
if [[ -e .git ]]; then echo 'Un historique Git existe déjà : publication initiale refusée.' >&2; exit 1; fi
sha256sum --check --status PUBLIC_MANIFEST.sha256
if find progress -type f ! -name .gitkeep -print -quit | grep -q .; then echo 'La publication initiale doit partir d’un dossier de progression vide.' >&2; exit 1; fi
account=$(gh api user --jq .login)
[[ "$account" =~ ^[A-Za-z0-9-]+$ ]]
repo="$account/PS1-Learning"
if gh repo view "$repo" --json nameWithOwner >/dev/null 2>&1; then echo "Dépôt $repo déjà présent; aucune modification." >&2; exit 1; fi
printf 'Nouveau dépôt PUBLIC : %s. Les futures réponses seront publiques.\n' "$repo"
git init -b main
# Do not leak a private e-mail in the initial commit.
uid=$(gh api user --jq .id)
git config --local user.name "$account"
git config --local user.email "$uid+$account@users.noreply.github.com"
# Stage only reviewed files, not arbitrary files in the extracted folder.
while IFS= read -r line; do git add -- "${line:66}"; done < PUBLIC_MANIFEST.sha256
git add -- PUBLIC_MANIFEST.sha256
# Upstream vendor bytes and Markdown blank lines are deliberately preserved.
git -c core.whitespace=-blank-at-eol,-blank-at-eof diff --cached --check
git commit -m 'Initial public PS1 learning project'
gh repo create "$repo" --public --source=. --remote=origin --push
gh repo view "$repo" --json nameWithOwner,url,visibility,defaultBranchRef
