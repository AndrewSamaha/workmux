#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash start-integration.sh [options] <new-integration-branch>

Create an integration worktree from origin's current GitHub default branch.

Options:
  --repo <path>             Target repository (default: caller's repository)
  --config <path>           Alternate workmux config (relative to caller)
  --profile <name>          Central profiles/<name>.json (exclusive with --config)
  --parent-session <name>   Tmux session receiving the integration window
  -h, --help                Show this help

Examples:
  bash /path/to/workmux/start-integration.sh feat/search
  bash /path/to/workmux/start-integration.sh --repo /path/to/repo feat/search
EOF
}

fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
workflow_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_path=$PWD
config_path=
profile=
parent_session=
branch=
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --repo|--config|--profile|--parent-session)
      [[ $# -ge 2 && -n "$2" && "$2" != -* ]] || { usage >&2; exit 2; }
      case "$1" in
        --repo) repo_path=$2 ;;
        --config) config_path=$2 ;;
        --profile) profile=$2 ;;
        --parent-session) parent_session=$2 ;;
      esac
      shift 2 ;;
    -*) usage >&2; exit 2 ;;
    *) [[ -z "$branch" ]] || { usage >&2; exit 2; }; branch=$1; shift ;;
  esac
done
[[ -n "$branch" ]] || { usage >&2; exit 2; }
[[ -z "$profile" || -z "$config_path" ]] || fail "Choose --profile or --config, not both."
if [[ -n "$profile" ]]; then
  command -v python3 >/dev/null || fail "python3 is required for repository profiles."
  [[ "$profile" =~ ^[a-zA-Z0-9_-]+$ ]] || fail "Invalid profile name."
  [[ -f "$workflow_root/profiles/$profile.json" ]] || fail "Profile not found: $profile"
  profile_config=$(python3 "$workflow_root/repo-profile.py" render "$profile") || fail "Could not render profile: $profile"
fi
for dependency in git gh workmux codex; do
  command -v "$dependency" >/dev/null || fail "$dependency is required."
done
git check-ref-format "refs/heads/$branch" >/dev/null || fail "Invalid integration branch."
for file in AGENTS.md workflow.md default-branch.sh .agents/skills/workmux-integration/SKILL.md; do
  [[ -f "$workflow_root/$file" ]] || fail "Workflow file missing: $workflow_root/$file"
done
# Resolve an explicit config relative to the caller before changing directories.
if [[ -n "$config_path" ]]; then
  [[ -f "$config_path" ]] || fail "Config file not found: $config_path"
  config_path="$(cd -- "$(dirname -- "$config_path")" && pwd -P)/$(basename -- "$config_path")"
fi
repo_root=$(git -C "$repo_path" rev-parse --show-toplevel) || fail "Select a Git repository with --repo <path>."
cd -- "$repo_root"
[[ -z "$(git status --porcelain)" ]] || fail "Commit or stash working-tree changes before starting integration."
if git show-ref --verify --quiet "refs/heads/$branch"; then
  fail "Branch already exists: $branch. Inspect git worktree list and resume with workmux open."
fi
[[ -z "$(git ls-files -- .workmux-local/)" ]] || fail ".workmux-local contains tracked files; resolve this before starting."
if [[ -z "$config_path" ]]; then
  if [[ -n "$profile" ]]; then
    config_path="$repo_root/.workmux-local/configs/$profile.yaml"
  elif [[ -f "$repo_root/.workmux.yaml" ]]; then
    config_path="$repo_root/.workmux.yaml"
  else
    config_path="$workflow_root/workmux.yaml"
  fi
fi
[[ -n "$profile" || -f "$config_path" ]] || fail "Config file not found: $config_path"

default_branch=$(bash "$workflow_root/default-branch.sh" "$repo_root")
[[ "$branch" != "$default_branch" ]] || fail "The integration branch must differ from the default branch."
if git ls-remote --exit-code --heads origin "refs/heads/$branch" >/dev/null 2>&1; then
  fail "Integration branch already exists on origin: $branch. Inspect it before resuming."
else
  remote_status=$?
  [[ $remote_status -eq 2 ]] || fail "Could not check origin for an existing integration branch."
fi
git fetch --no-tags origin "+refs/heads/$default_branch:refs/remotes/origin/$default_branch"
base_sha=$(git rev-parse --verify "refs/remotes/origin/$default_branch^{commit}")
if git show-ref --verify --quiet "refs/heads/$default_branch"; then
  git merge-base --is-ancestor "refs/heads/$default_branch" "$base_sha" ||
    fail "Local default branch is ahead/diverged. Follow $workflow_root/workflow.md recovery guidance."
fi

# Shared by this repository's worktrees, without editing tracked .gitignore files.
if ! git check-ignore --quiet .workmux-local/.ignore-check; then
  exclude_path=$(git rev-parse --git-path info/exclude)
  mkdir -p -- "$(dirname -- "$exclude_path")"
  printf '\n/.workmux-local/\n' >> "$exclude_path"
fi
git check-ignore --quiet .workmux-local/.ignore-check || fail "Repository ignore rules override the local state exclusion."
mkdir -p .workmux-local/prompts
if [[ -n "$profile" ]]; then
  mkdir -p .workmux-local/configs
  config_temp=$(mktemp "$config_path.XXXXXX")
  printf '%s\n' "$profile_config" > "$config_temp"
  mv -- "$config_temp" "$config_path"
fi
prompt_file=$(mktemp "$repo_root/.workmux-local/prompts/integration.XXXXXX")
cat > "$prompt_file" <<EOF
Use \$workmux-integration. Your role is INTEGRATION AGENT.
Read these central workflow files by absolute path:
- $workflow_root/AGENTS.md
- $workflow_root/.agents/skills/workmux-integration/SKILL.md
- $workflow_root/workflow.md
Also follow the target repository's applicable agent instructions.

Workflow root: $workflow_root
Source repository checkout: $repo_root
Repository remote: origin
Default branch and PR target: $default_branch
Dispatch base SHA: $base_sha
Integration branch: $branch
Effective workmux config: $config_path
Repository setup profile (empty means none): $profile
Requested parent session (empty means inherited placement): $parent_session
Kickoff prompt: $prompt_file

You are in a new integration worktree created from that fetched default-branch
commit. The original checkout's branch was not changed. Never merge task or
integration work into the local default branch. Tasks merge into $branch only.
Initialize .workmux-local/integration.md here with this context and verify the
actual worktree, branch, and notification target. Pass the absolute workflow
paths, effective config, role, and integration target in every task brief.
Ask for the feature goal and acceptance criteria before implementing or dispatching.
Coordinate shared services and run combined validation in this integration worktree.
Do not push or create a PR until requested. If workmux partially created this
worktree, inspect git worktree list and resume it rather than launching a duplicate.
EOF
if [[ -n "$profile" ]]; then
  cat >> "$prompt_file" <<EOF

Repository profile commands (run from the integration worktree):
  python3 "$workflow_root/repo-profile.py" setup "$profile" --worktree . --install
  python3 "$workflow_root/repo-profile.py" check "$profile" --worktree .
  python3 "$workflow_root/repo-profile.py" start "$profile" --worktree .
The creation hook provisions missing ignored configuration only. Dependencies
are installed explicitly. Do not start the application in task worktrees.
Record this profile and these commands in the handoff and every task brief.
EOF
fi
args=(add "$branch" --base "$base_sha" --config "$config_path" -P "$prompt_file")
if [[ -n "$parent_session" ]]; then
  args+=(--parent-session "$parent_session")
fi
printf 'Creating %s from origin/%s (%s).\n' "$branch" "$default_branch" "$base_sha" >&2
workmux "${args[@]}"
