# Agent guidance

For workmux integration or delegated task assignments, read
[`workflow.md`](workflow.md) and follow the
[`workmux-integration` skill](.agents/skills/workmux-integration/SKILL.md).
Repo default branches such as those named `main`, `master`, `development`, and
`development-2` are reserved for syncing with GitHub; never merge feature/task
work into the repo's default branches.
Task work merges into the integration feature branch, which reaches the default
branch through PR. Stop and follow workflow recovery guidance if local default
branch shows ahead/diverged commits.
Integration agents delegate feature implementation and corrections, then own
review, merging, and validation. Task agents commit their results, write a local
completion report, and notify the integration target supplied in their brief.
Integration agents monitor outstanding tasks and continue through review and
validation when notified; a `done` status alone does not mean acceptance.
