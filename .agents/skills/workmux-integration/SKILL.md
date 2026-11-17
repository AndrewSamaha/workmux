---
name: workmux-integration
description: Coordinate a feature integration branch and separate workmux task agents across GitHub repositories, including review, local merging, completion monitoring, and combined validation. Use for workmux integration assignments or delegated task briefs.
---

# Workmux integration

Locate the central workflow root from the kickoff, task brief, or existing
integration handoff. For a manually invoked copied skill, read
`git config --global --path workmux.workflowRoot`. If neither supplies an
existing directory, request its location; do not look for workflow files in the
target repo or assume the installed skill is still inside the workflow checkout.
Read `<workflow-root>/AGENTS.md` and `<workflow-root>/workflow.md`, the source of
truth for roles, dispatch, reports, monitoring, recovery, and delivery. Also
follow the target repository's applicable agent instructions.

Identify your role before acting. As a TASK AGENT, implement the supplied brief
directly in its worktree, run appropriate isolated checks, commit, atomically
write the specified completion report, and notify the exact integration target.
Leave dispatch, merging, shared-service checks, and publication to integration.

As an INTEGRATION AGENT, verify the intended worktree, branch, goal, and acceptance
criteria. Read `.workmux-local/integration.md` if present and reconcile it against
Git and live workmux status. Resume existing related tasks rather than launching
duplicates. For a new integration, use the central launcher, which discovers the
GitHub default with `default-branch.sh` and branches from its fetched commit.
Do not recreate an existing integration or switch/reset its branch.

Never merge into a local default branch. Delegate implementation and corrections
to separate workmux task worktrees from the committed integration branch. Supply
absolute central instruction paths, the TASK AGENT role, target repository,
recorded default branch, effective config path, exact integration notification
target, and task-local report path in every brief. Use explicit `--base` and
`--config` on task creation and `--into <integration-branch> --keep` on merging.
Do not commit unrelated user edits.

Track tasks across interruptions. Verify launches, monitor with bounded waits
and status/capture checks, and verify reports against committed diffs and check
results. Record acknowledgment by task handle and commit SHA. Continue through
review, corrections, merge, combined validation, and cleanup within the existing
authorization. Follow the workflow's completion protocol for delivery failures,
duplicate messages, and blocked tasks. A done status is not acceptance.

Keep the integration handoff and prompts under ignored `.workmux-local/` in the
integration worktree; task agents write their own completion reports. Record the
workflow root, repository identity, default branch, integration branch, base SHA,
effective config, and notification context so a new agent can resume. Coordinate
shared services and choose setup/check commands from the target repo's guidance.

Push or open a PR only when requested, targeting the recorded and verified GitHub
default branch in the correct repository. Synchronize local default branches only
by fast-forward in a suitable worktree. Stop on ahead/diverged commits and follow
central recovery guidance; never reset or merge blindly.
