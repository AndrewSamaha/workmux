#!/usr/bin/env bash
set -euo pipefail

# Pinned to origin so a configured gh default repository or GH_REPO cannot select a different repo.
[[ $# -le 1 ]] || { echo "Usage: bash default-branch.sh [repo-path]" >&2; exit 2; }
cd -- "${1:-.}"
git rev-parse --show-toplevel >/dev/null
# Read the configured URL before Git's insteadOf transport rewrites (which may
# point at a local mirror rather than a URL understood by GitHub CLI).
remote_url=$(git config --get remote.origin.url)
case "$remote_url" in
  https://*|http://*) repo_url=$remote_url ;;
  git@*:*) remote_path=${remote_url#git@}; repo_url="https://${remote_path%%:*}/${remote_path#*:}" ;;
  ssh://git@*) repo_url="https://${remote_url#ssh://git@}" ;;
  *) echo "Use a GitHub HTTPS or SSH origin URL for default-branch discovery." >&2; exit 1 ;;
esac
repo_url=${repo_url%.git}
default_branch=$(gh repo view "$repo_url" --json defaultBranchRef --jq '.defaultBranchRef.name')
if [[ -z "$default_branch" || "$default_branch" == null ]] ||
   ! git check-ref-format "refs/heads/$default_branch" >/dev/null 2>&1; then
  echo "GitHub did not return a valid default branch for origin. Check gh authentication and repository access." >&2
  exit 1
fi
printf '%s\n' "$default_branch"
