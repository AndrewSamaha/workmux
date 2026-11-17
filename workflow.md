# Agent-managed workmux integration workflow

Use this workflow across GitHub repositories. The launcher, agent guidance, and
skill source live in this central workflow checkout; Git operations, task work,
and validation happen in the selected target repository and its worktrees.
Each repository has its own integration branch and PR. Coordinate cross-repository
features through their goals, dependencies, and combined checks; never merge
branches between unrelated repositories.

## Roles and instruction locations

The integration agent delegates implementation and corrections to separate
workmux task worktrees. It owns review, local integration, validation, and cleanup.
Task agents implement directly, commit, write completion reports, and notify the
integration target supplied in their brief. They do not recursively dispatch.
Use workmux task sessions rather than in-process subagents for this workflow.
Maintaining this workflow package itself does not require task delegation.

Read the central `AGENTS.md` and this document using the absolute workflow root
supplied in the kickoff or handoff. A copied skill can find that root with
`git config --global --path workmux.workflowRoot`. Follow the target repository's
applicable AGENTS.md instructions for coding conventions and required checks.
Workflow paths refer to the central checkout; product paths refer to the current
target worktree. Do not look for workflow files inside the target repository.

Every task prompt must explicitly supply the central instruction paths and task
role. The central AGENTS.md is not automatically discovered in unrelated repos.
See [README.md](README.md) for copying the skill into user-level discovery.

## Default branch and ownership

Use the logic of the `showdefaultbranch` shell alias: ask GitHub for
`defaultBranchRef.name`. The shared helper pins the query to the target's origin
URL so GitHub CLI defaults or GH_REPO cannot silently select another repository:

```sh
bash /absolute/path/to/workmux/default-branch.sh /absolute/path/to/target-repo
```

The helper uses `gh repo view <origin-repository-url> --json defaultBranchRef
--jq '.defaultBranchRef.name'`. It does not source .zshrc or guess branch names.
GitHub access and an origin remote are required. Query failures stop setup.

The detected default branch is the integration starting point and PR target.
It can have any valid branch name, including names with slashes. The launcher
has no `--base` option. Record the resolved name and base SHA in the handoff;
when resuming, reconcile changes rather than silently changing the PR target.

Local default branches are reserved for synchronization. Never merge task or
integration branches into them locally. Task branches merge into the integration
feature branch using explicit `--into <integration-branch>`; the feature reaches
the default branch through a GitHub PR. Never rely on workmux's implicit merge
or creation base, even if a global config sets one.

## Start the integration branch

From any directory, select the repository explicitly:

```sh
bash /absolute/path/to/workmux/start-integration.sh \
  --repo /absolute/path/to/target-repo feat/my-new-feature
```

From inside the intended repository, omit `--repo`. The launcher resolves its
workflow files relative to itself, checks for a clean target checkout, discovers
the default branch, checks local and remote integration-branch collisions, and
fetches the default branch from origin. It creates the integration worktree from
that exact fetched commit using an explicit workmux `--base <sha>`.

The source checkout stays on its current branch. No local default checkout,
pull, merge, or reset is required. A local default branch may be behind origin;
if it has ahead or divergent commits, stop and follow recovery guidance. The
launcher does not need to create a missing local default branch.

It also excludes `.workmux-local/` through the target repository's local Git
exclude file, shared by its worktrees, without modifying tracked .gitignore.
It refuses tracked local state or ignore rules that prevent the exclusion.
The kickoff prompt remains in the source checkout's ignored prompt directory
for recovery. Integration handoff state belongs in the new integration worktree.

The integration agent verifies its worktree and branch, initializes the handoff,
and asks for the feature goal and acceptance criteria before dispatching work.
Both workmux and Codex must be installed; run in the intended tmux/workmux
context. Use `--parent-session <name>` when explicit tmux window placement is
needed. Session-mode configurations should use their own placement instead.

## Repository configuration and services

Configuration selection is explicit and retained in the handoff:

An explicit `--profile <name>` instead selects `profiles/<name>.json` in the
central workflow checkout and renders its workmux settings to an ignored config
under the source checkout's `.workmux-local/configs/`. It cannot be combined with
`--config`. Profile hooks provision missing ignored configuration only, using
`WM_PROJECT_ROOT` and `WM_WORKTREE_PATH`; existing destination files are preserved.
Keep the generated absolute config path in the handoff and all task briefs.
Without `--profile`, configuration selection remains:

1. `--config <path>` selects an alternate config, resolved relative to the caller.
2. Otherwise use the target repository root's `.workmux.yaml` when present.
3. Otherwise use this package's `workmux.yaml` (Codex agent and shell panes).

The selected config must provide a Codex `<agent>` pane for prompt delivery.
Repository configs retain their hooks and file-copy settings; inspect these
before use. The fallback does not start services, copy environment files, or
symlink dependencies. Global settings still merge according to workmux rules.
An alternate config replaces project-config selection; do not assume it layers
on top of the target repo config. Put centrally maintained repository profiles
where desired and select them through `--config`.

Pass the same absolute effective config to task creation and recovery commands.
If a config lives in a source checkout, keep that path available throughout the
assignment. Verify paths before resuming; don't silently change configuration.

Read target-repository setup instructions to choose dependencies, environment
files, build checks, and runtime startup. Provision ignored files deliberately;
worktrees do not isolate ports, databases, credentials, or external services.
The integration worktree owns shared runtime and combined validation. Task
agents run suitable isolated checks and coordinate before using shared services.
Do not copy local handoff state, print credentials, or commit environment files.

For selected repository profiles, use `python3 <workflow-root>/repo-profile.py
setup <profile> --worktree . --install` to explicitly install dependencies and
provision missing local files. Only integration runs `check` and `start` against
shared services. The Gary profile reuses existing Redis and launches the app
without Compose; task worktrees must not start competing servers. Record the
profile and startup command in the handoff and task briefs. Profiles are recipes,
not secrets. See README.md for profile fields, existing-worktree adoption, and
startup limitations. Use the repo's supported runtime version (Gary: Node 22.17.0).

## Local handoff state

Maintain `.workmux-local/integration.md` only in the integration worktree.
Keep task prompts in `.workmux-local/prompts/` there, using absolute prompt paths
for workmux. Task worktrees write their own completion reports, not integration
handoff copies. Verify local state is ignored in each worktree before writing it.

Create the handoff at initialization and update it after dispatch, review,
merge, validation, and cleanup. Record current operational context:

- Feature goal, acceptance criteria, repository origin URL and source checkout.
- Absolute workflow root, workflow revision, effective config path, default/PR
  target branch, initial base SHA, integration branch, worktree, and current SHA.
- Actual integration handle or pane ID and project session for notifications.
- Task handles, branches, worktree paths, dispatch bases, prompt/report paths,
  notification targets, latest status, and any outstanding corrections.
- Completion acknowledgments keyed by task handle plus commit SHA, reviewed and
  merged commits, validation commands/results and tested SHA, cleanup state.
- Shared runtime details, next actions, blockers, and publishing authorization.

Keep it concise and secret-free. Never force-add it. A fresh agent reads the
handoff and central workflow, verifies Git and live workmux state, and resumes
existing tasks rather than launching duplicates. The handoff may be stale and
does not expand authorization. If it belongs to another integration branch,
preserve it and reconcile context before overwriting it. Point agents opened
elsewhere to the actual integration worktree; handoffs do not travel with branches.

## Interrupted setup and reopening

Successful fetches and local exclusions remain applied if later setup fails.
Inspect `git worktree list`, branch refs, and workmux status before retrying.
Do not automatically remove partially created worktrees or reset branches.
If the integration worktree exists, reopen it with the recorded config and
retained kickoff prompt, using the actual workmux handle:

```sh
workmux open <integration-handle> --config <absolute-effective-config> \
  -P <absolute-kickoff-prompt>
```

Reopening does not guarantee dependency or ignored-file provisioning. Inspect
what exists and use the repository's setup instructions for recovery. Task
worktrees must start from committed integration changes, not uncommitted files.

## Delegate through the integration agent

The user can request delegation directly:

> Fix the dashboard issue in a separate workmux worktree. Review and merge the result into this integration branch, then test it here.

This request authorizes the integration agent to create the task branch and worktree, write and deliver the task prompt, launch a task agent, review its committed work, merge it into the current integration branch, and run appropriate integration checks. The user does not need to create task branches, write prompt files, or run workmux commands manually. Pushes and PR creation require a user request, which may be given as part of the original task.

## Integration agent responsibilities

1. **Prepare a committed starting point.** Identify the branch checked out in the integration worktree and use it explicitly as the integration branch. Commit completed, relevant integration-agent edits before dispatching. Do not automatically commit unrelated user edits; clarify their handling when they affect the task. Uncommitted changes are not included in new task branches.

2. **Write a self-contained task brief.** Include the problem, expected behavior, relevant files and context, scope boundaries, acceptance criteria, and required local checks. Tell the task agent to commit its finished work, save the completion report described below, and notify the integration agent. Identify the role as TASK AGENT. Include absolute paths to the central AGENTS.md, skill, and workflow; the target repository and its applicable instructions; the recorded default branch; and the effective config path. Tell the task agent to implement directly without dispatching other agents. Include the exact integration handle (or unambiguous pane ID), project session, task handle, and absolute task-local report path in every brief. Do not infer the notification target from a branch name. The integration agent owns merging and shared-service testing. Store the prompt outside tracked source, or in an ignored location, so it does not become an accidental product change.

3. **Dispatch the task.** Run workmux from the target integration worktree. Choose a unique task branch and create its worktree from the committed integration branch. Pass the prompt file to the new agent:

   ```sh
   workmux add <task-branch> --base <integration-branch> --config <absolute-effective-config> -b -P <prompt-file> --parent-session <project-session>
   ```

   For example, use `feat/my-new-feature-dashboard` as the task branch and `feat/my-new-feature` as its base. Independent tasks may run concurrently. Each branch starts from the integration branch's committed state at dispatch time; existing task branches do not automatically receive later integration changes. For dependent tasks, dispatch after the prerequisite is merged, or explicitly coordinate an update of the task branch.

   Use the intended project session from user instructions or known integration context. Include it with `--parent-session` when needed for placement; ask if placement is required but unknown rather than guessing. Confirm launch with `workmux wait <handle> --status working --timeout 30`, then inspect status/output if the agent has already finished or the wait times out.

   Track every dispatched handle in the handoff until reviewed, merged, and validated or explicitly canceled. Monitor with `workmux status`, `workmux capture`, and bounded `workmux wait` calls; use `--any` when multiple tasks remain. A canceled wait or intervening user message does not cancel tasks. Reconcile statuses and resume monitoring after handling the interruption, keeping the user informed. A `done` status means the session stopped working, not that its implementation has been accepted. Follow the completion and monitoring protocol below; do not end integration work merely because dispatch succeeded or a progress update was delivered.

4. **Review and integrate one task at a time.** Inspect the agent's status, captured output, committed diff, and check results. Request corrections when needed. Merge accepted work into the integration branch explicitly:

   ```sh
   workmux merge <handle> --into <integration-branch> --keep
   ```

   Do not rely on the default merge target: it may be the repository default branch. Resolve overlapping edits deliberately and review the combined result. `--keep` retains the task worktree, branch, and tmux window for follow-up work.

5. **Validate in the integration worktree.** Run appropriate checks against the combined changes. Reload or restart the single running app/server as needed and run integration or E2E checks here. Worktrees do not isolate databases, ports, or external services.

6. **Iterate with the same task agent.** Send concrete failures and logs with `workmux send <handle> ...`. Have the agent commit its correction, review it, merge the additional commits using `--into <integration-branch> --keep`, and rerun the affected checks. Coordinate any integration-branch updates the task agent needs before further work.

7. **Clean up after validation.** Once the task is accepted and integration checks pass, remove its retained worktree/window with `workmux remove <handle>`. Keep the integration branch for final review and delivery.

## Task agent responsibilities

- Implement only the assigned task in its own worktree.
- Run the relevant compilation, syntax, build, and unit checks available locally.
- Do not start a competing app/server or run tests against shared services without coordination.
- Commit the completed work and report the result to the integration agent.
- Leave merging, integration testing, and publishing to the integration agent.

## Completion notification and durable report

Each task brief must provide a notification target for the integration agent and
an absolute report path in the task worktree, normally
`.workmux-local/completion.md`. This is a task result, not a copy of
`.workmux-local/integration.md`. Never copy or commit either local file.

After committing, the task agent writes its report before sending the completion
message. Write a temporary file next to the report and rename it into place so
readers never see a partial report. Include:

- Task handle, branch, worktree, dispatch base SHA, and completed commit SHA.
- Result: `ready_for_review` or `blocked`; summarize changes or the blocker.
- Exact check commands and outcomes, including skipped checks and failures.
- Remaining concerns, runtime restart requirements, and shared-service checks
  that the integration agent must perform.
- Notification target and delivery outcome; no secrets or environment contents.

On corrections, replace the report with the latest result after committing and
send a new notification. Use task handle plus completed commit SHA as the
completion identity; repeated notifications for that identity are harmless.
A blocked report may use the current HEAD and must explain what input is needed.

Send a concise prompt through workmux to the target provided in the brief:

```sh
workmux send <integration-handle-or-pane-id> \
  'READY_FOR_REVIEW task=<task-handle> commit=<sha> report=<absolute-path>; review, integrate, and validate this result.'
```

Use `TASK_BLOCKED` instead of `READY_FOR_REVIEW` when user input or an external
change is required. This agent-to-agent notification is authorized by task
dispatch. It does not authorize publishing or messages to external services.
A task agent must not merge its own branch.

`workmux send` delivers a prompt; successful delivery is not acknowledgment or
acceptance. Check its exit status. If delivery fails, record the error in the
report, retry once after checking the target status, and leave the report for the
integration agent's monitoring fallback. Never send input into a permission
dialog or guess another pane. Do not use `--wait` on completion notifications:
waiting for integration to finish can create a circular wait. Idle-session wakeup
and busy-session delivery must be verified in the local agent setup before
relying on notifications alone.

## Integration monitoring and acknowledgment

After dispatch, keep monitoring outstanding tasks until they are reviewed,
integrated and validated, or explicitly canceled. Use bounded waits of at most
30 seconds, inspect status and capture after each timeout, and check for
`waiting` tasks that need approval or clarification:

```sh
workmux wait <task-handle> --status done --timeout 30
# For multiple outstanding tasks:
workmux wait <task-a> <task-b> --status done --any --timeout 30
```

Remove completed handles from the wait set while reviewing them; otherwise
`--any` can repeatedly return the same completion. Read the durable report and
verify its SHA against Git, the committed diff, and captured output. If a task
is done without a report, request the report from the same task agent rather
than treating it as accepted. A blocked report calls for resolving the blocker,
not merging unfinished work.

On a notification or discovered completion, record acknowledgment in the
integration handoff keyed by task handle and SHA. Duplicate messages must not
repeat a merge. Acknowledgment means the result has been received; acceptance
requires review and combined validation. Continue directly through review,
explicit-target merge, integration validation, and cleanup within the existing
user authorization. Request corrections from the same task agent when needed.

User messages interrupt monitoring without canceling tasks. Answer progress
questions briefly and resume monitoring unless the user explicitly pauses or
changes the assignment. After a restart or context interruption, reconcile all
recorded handles, current Git commits, reports, and live workmux statuses before
proceeding. If the integration session ends, notifications and task reports must
remain discoverable through the local handoff; an idle session is not assumed
to be actively polling.

## Publish the combined feature

Push and create a PR only when requested. Use the default branch and repository
identity recorded and verified for this integration, with explicit destinations:

```sh
git push -u origin <integration-branch>
gh pr create --repo <origin-repository-url> \
  --base <recorded-default-branch> --head <integration-branch>
```

Before publication, verify that origin still identifies the intended repository
and the GitHub default still matches the recorded target using the shared helper.
If it changed, reconcile the assignment before retargeting or publishing.

After GitHub merges the PR, fetch origin's default branch. When synchronizing a
local default branch, use its owning worktree with a clean checkout and explicit
`git merge --ff-only refs/remotes/origin/<default-branch>`. If it is not checked
out anywhere, switch to it only in a suitable clean checkout. Never switch away
from active integration work merely to synchronize a default branch.

A squash merge creates new commit identities. Because the local default branch
never received feature commits, synchronization should fast-forward cleanly.
A failed fast-forward or ahead/diverged local branch calls for recovery.

## Recover a local default branch with ahead or divergent commits

Do not pull, merge, rebase, or reset blindly. Inspect `git status -sb`,
`git worktree list`, the all-branch commit graph, and the commits in
`refs/remotes/origin/<default-branch>..<default-branch>`. Determine whether
those commits contain ongoing work, whether other worktrees depend on them,
and whether the remote already includes their file changes.

Preserve needed work on a separate branch or worktree. If local commits merely
duplicate already-published changes, preserve a backup reference before any
alignment. Only realign after verifying clean state, the intended remote,
and that all needed changes and active feature work remain recoverable. Never
use an automatic hard reset as launcher recovery. Re-run setup after resolving
the local divergence; ongoing integrations resume from their handoff instead.
