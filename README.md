# Shared workmux integration workflow

Keep this checkout as the source for the launcher, agent guidance, workflow,
and integration skill. Target repositories do not need copies of these files.
The checkout currently lives at `/Users/asamaha/Workspaces/workmux`; `~/workmux`
is also a valid location if you move or clone it there.

## Requirements

Install Git, GitHub CLI (`gh`), workmux, and Codex. Authenticate `gh` for the
repositories you use and run the launcher in your intended tmux/workmux context.
The target repository must have a GitHub origin remote and a clean working tree.
The workflow uses workmux's `--base`, `--config`, prompt-file, explicit-target
merge, status, capture, send, and wait support.

## Copy the integration skill

Run these commands once, setting `workflow_root` to this checkout's actual path:

```sh
workflow_root=/Users/asamaha/Workspaces/workmux
mkdir -p "$HOME/.agents/skills"
cp -R "$workflow_root/.agents/skills/workmux-integration" "$HOME/.agents/skills/"
git config --global workmux.workflowRoot "$workflow_root"
```

Check whether `$HOME/.agents/skills/workmux-integration` already exists before
copying; preserve any local modifications and replace it deliberately rather
than nesting another copy. After updating this package, refresh the installed
`SKILL.md` with:

```sh
cp "$workflow_root/.agents/skills/workmux-integration/SKILL.md" \
  "$HOME/.agents/skills/workmux-integration/SKILL.md"
```

The copied skill uses `workmux.workflowRoot` for manual invocations. Launcher and
task prompts also supply absolute workflow paths, so the instructions remain in
this checkout. If the checkout moves, update that Git setting. Start a fresh
agent session if the installed skill is not yet visible. Installation is a
manual step; the launcher does not edit your shell, global Git settings, or
installed skills.

## Start a feature

From the intended repository:

```sh
bash /Users/asamaha/Workspaces/workmux/start-integration.sh feat/my-feature
```

Or from the workspace containing several repositories:

```sh
bash /Users/asamaha/Workspaces/workmux/start-integration.sh \
  --repo /Users/asamaha/Workspaces/some-repo feat/my-feature
```

No `--base` is needed. Like the `showdefaultbranch` alias in `.zshrc`, discovery
uses `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`.
The shared [default-branch.sh](default-branch.sh) helper explicitly selects the
origin repository, including when `gh` has a different default repo configured.
The detected default is both the starting branch and PR target; there is no
branch-name fallback. This workflow intentionally targets GitHub repositories.

The launcher fetches that branch and creates a separate integration worktree
from its exact commit. It does not switch the source checkout's branch or
update its local default branch. Ahead/diverged local default branches stop
setup for inspection. Existing local or origin integration branches also stop
setup so you can resume deliberately.

The new integration agent asks for the feature goal and acceptance criteria,
then delegates implementation, reviews commits, merges into the feature branch,
and validates the combined result. Publishing requires a user request.

## Configuration

The launcher selects an explicit `--config`, the target root's `.workmux.yaml`,
or this package's [workmux.yaml](workmux.yaml), in that order. Explicit config
paths are relative to the directory where you invoke the launcher. The fallback
provides Codex and shell panes without automatic environment copying, dependency
symlinking, or service startup. Workmux global settings still apply according to
its configuration rules. Repository configs must provide a Codex `<agent>` pane.

For centrally stored repository settings:

```sh
bash /Users/asamaha/Workspaces/workmux/start-integration.sh \
  --repo /absolute/path/to/repo \
  --config /absolute/path/to/repo-workmux.yaml \
  --parent-session my-project feat/my-feature
```

Use `--parent-session` for tmux window placement; omit it for session-mode setups.
The effective absolute config path is passed to subsequent task creation and
recovery commands. Choose environment provisioning and checks from the target
repo's instructions. Worktrees share access to services and databases.

## Local state and recovery

### Repository profiles

Store local, per-repository setup recipes in `profiles/<name>.json` in this
workflow checkout. The `profiles/.gitignore` file is kept in source control so
fresh clones retain the directory, while its other contents stay local and
ignored. Create or privately restore the profiles you need before selecting
them; profile recipes are not included in a clone. A missing profile stops the
launcher; it does not fall back to another configuration.

Profiles describe each repository's local file locations, dependency commands,
environment, shared-service checks, and application startup. Keep secrets in
the original repository's ignored local config or external credential store;
profile files should contain paths and commands, never secret values.

Select a profile by its filename without `.json`:

```sh
bash /Users/asamaha/Workspaces/workmux/start-integration.sh \
  --repo /Users/asamaha/Workspaces/gary-ql --profile gary-ql feat/my-feature
```

`--profile` and `--config` are mutually exclusive. A selected profile replaces
project configuration; without it, existing configuration selection is unchanged.
The launcher renders the profile's `workmux` settings into an ignored config
under the source checkout's `.workmux-local/configs/`. Keep that source checkout
available: task creation and reopening must use the same absolute config path.
The generated hook uses absolute tool paths, so re-render after moving this
workflow checkout. Reopening an existing pane does not automatically run setup.

Creation hooks copy only missing ignored files from workmux's `WM_PROJECT_ROOT`
(the repository's main worktree). They never overwrite existing configuration,
install dependencies, or start services. Task worktrees get their own copies.
Profiles hold paths and commands, never credentials or configuration contents.
Use a separate profile for each repository's local file locations and commands.

When adding a profile, use an existing local profile as a starting point and
adjust these fields for the target repository:

| Field | Purpose |
| --- | --- |
| `copy` | Relative paths of ignored config files to copy from the main worktree when missing. |
| `install` | Dependency installation command as an argument array. |
| `dependency_paths` | Files or executables required before starting the app. |
| `environment` | Non-secret environment variables applied to checks and startup. |
| `services` | Shared services and their read-only `check` command arrays; use `[]` when none are needed. |
| `port` | Optional port override variable (`environment`) and default port (`default`). |
| `prestart` | Optional command array to run before starting the app. |
| `start` | Application startup command as an argument array. |
| `workmux` | Agent/pane layout and workmux settings; retain a Codex `<agent>` pane. |

Validate a new recipe with `repo-profile.py render <name>`, then run setup,
check, and startup in its integration worktree. Record the selected profile
and rendered config path in the handoff. Application-specific examples below
describe the local Gary, Premier UI, and Command Center recipes; recreate those
files locally if they are absent from a fresh checkout.

For an existing worktree, or to install its own dependencies:

```sh
python3 /Users/asamaha/Workspaces/workmux/repo-profile.py setup gary-ql --worktree . --install
python3 /Users/asamaha/Workspaces/workmux/repo-profile.py check gary-ql --worktree .
python3 /Users/asamaha/Workspaces/workmux/repo-profile.py start gary-ql --worktree .
```

`setup` defaults to the main worktree as the configuration source; `--source`
selects another worktree in the same repository. Existing destination files are
preserved. Omit `--install` to provision configuration without running npm.
Commands require Python 3.9+ and also accept `--help`.

The Gary profile copies `src/config/local.json`, uses `npm install` when explicitly
requested, and checks the existing `gary-ql-redis` container with `redis-cli ping`.
`check` verifies files, dependencies, service availability, and a free app port.
`start` performs those checks, generates GraphQL types, then runs Gary's existing
nodemon/Node command directly, bypassing the Compose step in `npm start`.
It uses `NODE_ENV=local` and the existing `SERVER_PORT` override (default 8003).
Stop it with Ctrl-C. It does not create or remove Redis containers.

Only the integration worktree starts the application. Task agents use isolated
checks; shared services and databases are still shared across all worktrees.
If another Gary process owns the port, stop it deliberately or choose a free
`SERVER_PORT`. Startup preflight passing does not guarantee that all downstream
databases and APIs are reachable; inspect the app logs and readiness separately.

To adopt a profile in an existing integration, run setup, render its config with
`repo-profile.py render <name>` into an ignored source-checkout config path, and
record the new effective config and profile in the integration handoff before
dispatching tasks. Do not recreate the integration worktree.

The launcher adds `/.workmux-local/` to the target's local Git exclusion when
needed. It does not edit tracked `.gitignore` files. Kickoff prompts stay in the
source checkout's ignored directory; the integration handoff stays in the new
integration worktree. Task worktrees keep their own completion reports.

On partial setup, inspect `git worktree list` and workmux status before retrying.
Reopen existing worktrees with the recorded config and kickoff prompt rather
than creating duplicates. See [workflow.md](workflow.md) for dispatch, completion
notifications, monitoring, publication, and recovery. [AGENTS.md](AGENTS.md)
contains the shared agent rules.

## Validation

Run the isolated launcher checks with:

```sh
python3 -m unittest discover -s tests -v
```

They use disposable Git repositories and fake GitHub/workmux/Codex commands;
they do not contact GitHub or launch agents, tmux windows, or services.

### Premier UI profile

Use `--profile premier-ui` for new integrations. For an existing integration,
run `repo-profile.py setup premier-ui --worktree <path> --install`, render its
config into an ignored `.workmux-local/configs/` path, and record that absolute
path as the effective config for subsequent workmux commands.

Premier UI pins Node 20.18.0 and npm 11.4.1 through Volta. The profile copies only
missing `src/app/config/local.json` overrides and installs a separate dependency
tree using `npm ci --legacy-peer-deps`, matching repository CI. Its `.env` and
vendored styleguide are tracked; the database codegen environment is not needed
for startup and is not copied. Existing user registry authentication remains
external to the profile.

`repo-profile.py start premier-ui --worktree <path>` checks dependencies and a
free `SERVER_PORT` (default 3000), then runs exactly `NODE_ENV=qa npm start`.
No shared containers or separate codegen step are required. The generic
`prestart` profile field is optional; when provided (as for Gary), failure still
prevents startup. Premier's npm script starts Rspack and its existing Prettier
watcher, so inspect startup compilation and HTTP readiness rather than treating
the watcher as proof of success. The normal local endpoint is
`http://127.0.0.1:3000`; backend, MFE, and authentication availability require
separate checks.

### Command Center profile

Use `--profile command-center` for new integrations. To adopt an existing
integration without recreating it:

```sh
python3 /Users/asamaha/Workspaces/workmux/repo-profile.py setup command-center --worktree . --install
mkdir -p .workmux-local/configs
python3 /Users/asamaha/Workspaces/workmux/repo-profile.py render command-center > .workmux-local/configs/command-center.yaml
python3 /Users/asamaha/Workspaces/workmux/repo-profile.py check command-center --worktree .
python3 /Users/asamaha/Workspaces/workmux/repo-profile.py start command-center --worktree .
```

Verify `.workmux-local/` is ignored first, and record the rendered absolute path
in the integration handoff and future task briefs. This profile pins its recipe
to the repository's Volta runtime (Node 20.18.0/npm 11.4.1), uses
`npm ci --legacy-peer-deps` (the Docker dependency strategy), and copies only
missing ignored `src/app/config/local.json` from the original checkout. The
tracked `.env` and environment JSON files need no copying. Existing overrides
and their modes are retained; newly provisioned configuration uses mode 0600.
Private package registry authentication must already be configured externally.
No dependency symlinks, containers, or database codegen are required.

Startup runs `NODE_ENV=qa-gcp npm start`, including its existing Rspack and
Prettier watcher. Local overrides merge into the selected environment, so review
those privately when diagnosing backend behavior. Command Center uses `PORT`
(default 3001), independently of Premier UI's `SERVER_PORT` (3000) and Gary's
8003. If needed, set the same free `PORT` for both `check` and `start`, for example
`PORT=3002 python3 /Users/asamaha/Workspaces/workmux/repo-profile.py start command-center --worktree .`.
The normal direct endpoint is `http://127.0.0.1:3001`; the README's
`commandcenterlocal.mountain.com` alias requires separate local DNS/proxy setup.
Only integration starts shared services, after checking the actual shell pane
and listeners. Confirm Rspack compilation and HTTP page/assets separately from
the watcher's status. Authentication, backend APIs, and remote MFEs need their
own connectivity checks; do not enter credentials for a startup smoke check.
