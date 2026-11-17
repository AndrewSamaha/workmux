# Agent guidance

For integration or task assignments, read this directory's `workflow.md` and
`.agents/skills/workmux-integration/SKILL.md` using the absolute workflow root
supplied in the kickoff, task brief, or handoff. Product paths resolve in the
target worktree. Follow that repository's applicable agent instructions too.
These central files need not be copied into target repositories.

Discover origin's GitHub default branch through `default-branch.sh`, which uses
the showdefaultbranch alias query. Record the result; do not assume a branch
name. Never merge feature/task work into local default branches. Task work
merges explicitly into the integration feature branch, which reaches the default
branch through PR. Stop if a local default branch has ahead/diverged commits.

Integration agents delegate implementation and corrections through workmux,
then own review, merging, validation, and cleanup. Task agents implement directly,
commit, write a local completion report, and notify the exact integration target
supplied in their brief. They do not dispatch other agents or merge themselves.
Integration agents monitor outstanding tasks through acceptance and validation;
a `done` status alone does not mean acceptance. Maintaining this workflow package
itself does not require delegation.
