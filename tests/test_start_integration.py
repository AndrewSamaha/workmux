"""Exercise launcher behavior with real Git and stubbed external commands."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


WORKFLOW = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="workmux tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.repo = self.root / "target repo"
        self.remote = self.root / "origin.git"
        self.log = self.root / "launch.json"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GH_REPO": "wrong/ambient-repository",
            "TEST_LOG": str(self.log),
            "TEST_WORKTREE": str(self.root / "integration worktree"),
        }
        self.stub("gh", """import os, sys
assert sys.argv[1:] == ['repo', 'view', 'https://github.com/example/target',
                       '--json', 'defaultBranchRef', '--jq', '.defaultBranchRef.name'], sys.argv
sys.exit(1) if os.environ.get('TEST_GH_FAIL') else None
print(os.environ['TEST_DEFAULT'])
""")
        self.stub("codex", "raise AssertionError('Codex must not be launched by tests')\n")
        self.stub("workmux", """import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
prompt = pathlib.Path(args[args.index('-P') + 1])
pathlib.Path(os.environ['TEST_LOG']).write_text(json.dumps({
    'args': args, 'cwd': os.getcwd(), 'prompt': prompt.read_text(), 'prompt_path': str(prompt)
}))
subprocess.run(['git', 'worktree', 'add', '-b', args[1], os.environ['TEST_WORKTREE'],
                args[args.index('--base') + 1]], check=True)
sys.exit(int(os.environ.get('TEST_WORKMUX_EXIT', '0')))
""")

    def stub(self, name, code):
        path = self.bin / name
        # Use the test interpreter so execution does not depend on PATH Python.
        import sys

        path.write_text(f"#!{sys.executable}\n" + code)
        path.chmod(0o755)

    def run_command(self, *args, cwd=None, check=True):
        return subprocess.run(
            args, cwd=cwd or self.root, env=self.env,
            text=True, capture_output=True, check=check,
        )

    def git(self, *args):
        return self.run_command("git", "-C", str(self.repo), *args).stdout.strip()

    def initialize(self, default="development-2"):
        self.env["TEST_DEFAULT"] = default
        self.run_command("git", "init", "--initial-branch", default, str(self.repo))
        self.git("config", "user.name", "Workmux Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        (self.repo / "tracked.txt").write_text("initial\n")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.run_command("git", "init", "--bare", str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", default)
        self.git("remote", "set-url", "origin", "https://github.com/example/target.git")
        self.git("config", f"url.{self.remote.as_uri()}.insteadOf", "https://github.com/example/target.git")
        self.git("switch", "-c", "existing-work")
        return self.git("rev-parse", "HEAD")

    def launch(self, *args, explicit_repo=True):
        command = ["bash", str(WORKFLOW / "start-integration.sh")]
        if explicit_repo:
            command += ["--repo", str(self.repo)]
        command += list(args)
        return self.run_command(*command, cwd=self.root if explicit_repo else self.repo, check=False)

    def assert_not_launched(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.log.exists())

    def test_default_names_and_source_checkout_preserved(self):
        # Each invocation needs independent repositories and feature refs.
        for default in ("main", "master", "development", "development-2", "release/current"):
            with self.subTest(default=default):
                case = LauncherTests()
                case.setUp()
                self.addCleanup(case.doCleanups)
                sha = case.initialize(default)
                result = case.launch("feat/test")
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads(case.log.read_text())
                self.assertEqual(case.git("branch", "--show-current"), "existing-work")
                self.assertEqual(record["args"][record["args"].index("--base") + 1], sha)
                self.assertIn(f"Default branch and PR target: {default}", record["prompt"])
                self.assertIn(str(WORKFLOW / "workflow.md"), record["prompt"])
                self.assertIn("Use $workmux-integration", record["prompt"])
                self.assertTrue(Path(record["prompt_path"]).exists())
                case.git("check-ignore", ".workmux-local/integration.md")
                case.run_command("git", "-C", case.env["TEST_WORKTREE"], "check-ignore", ".workmux-local/completion.md")
                self.assertEqual(case.git("status", "--porcelain"), "")
                self.assertFalse((case.repo / ".gitignore").exists())

    def test_ssh_origin_formats(self):
        self.initialize()
        for url in ("git@github.com:example/target.git", "ssh://git@github.com/example/target.git"):
            self.git("remote", "set-url", "origin", url)
            result = self.run_command("bash", str(WORKFLOW / "default-branch.sh"), str(self.repo))
            self.assertEqual(result.stdout.strip(), "development-2")

    def test_explicit_config_and_placement(self):
        self.initialize()
        config = self.root / "custom config.yaml"
        config.write_text("agent: codex\n")
        result = self.launch("--config", config.name, "--parent-session", "my-project", "feat/test")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.log.read_text())["args"]
        self.assertEqual(args[args.index("--config") + 1], str(config))
        self.assertEqual(args[args.index("--parent-session") + 1], "my-project")

    def test_central_profile_is_rendered_and_recorded(self):
        self.initialize()
        result = self.launch("--profile", "gary-ql", "feat/test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads(self.log.read_text())
        config_path = Path(record["args"][record["args"].index("--config") + 1])
        config = json.loads(config_path.read_text())
        self.assertIn('"$WM_PROJECT_ROOT"', config["post_create"][0])
        self.assertIn('"$WM_WORKTREE_PATH"', config["post_create"][0])
        self.assertIn("Repository setup profile (empty means none): gary-ql", record["prompt"])
        self.assertIn('repo-profile.py" start "gary-ql"', record["prompt"])
        self.git("check-ignore", str(config_path))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_invalid_or_conflicting_profile_does_not_launch(self):
        self.initialize()
        for options in (("--profile", "../outside"), ("--profile", "missing"),
                        ("--profile", "gary-ql", "--config", "some.yaml")):
            self.assert_not_launched(self.launch(*options, "feat/test"))

    def test_caller_repo_and_project_config(self):
        self.initialize()
        config = self.repo / ".workmux.yaml"
        config.write_text("agent: codex\n")
        self.git("add", ".workmux.yaml")
        self.git("commit", "-m", "project configuration")
        result = self.launch("feat/test", explicit_repo=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.log.read_text())["args"]
        self.assertEqual(args[args.index("--config") + 1], str(config))

    def test_default_checked_out_in_another_worktree(self):
        self.initialize()
        self.git("worktree", "add", str(self.root / "default worktree"), "development-2")
        result = self.launch("feat/test")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_local_default(self):
        self.initialize()
        self.git("branch", "-D", "development-2")
        result = self.launch("feat/test")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_default_ahead_stops(self):
        self.initialize()
        self.git("switch", "development-2")
        self.git("commit", "--allow-empty", "-m", "local-only")
        self.git("switch", "existing-work")
        result = self.launch("feat/test")
        self.assert_not_launched(result)
        self.assertIn("ahead/diverged", result.stderr)
        self.assertEqual(self.git("branch", "--show-current"), "existing-work")

    def advance_remote(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        # A sibling commit makes divergence tests meaningful without checkout.
        sha = self.git("commit-tree", tree, "-p", "HEAD", "-m", "remote advance")
        # Bypass origin so the local remote-tracking ref stays stale until fetch.
        self.git("push", str(self.remote), f"{sha}:refs/heads/development-2")
        return sha

    def test_local_default_behind_uses_fetched_commit(self):
        initial = self.initialize()
        sha = self.advance_remote()
        result = self.launch("feat/test")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.log.read_text())["args"]
        self.assertEqual(args[args.index("--base") + 1], sha)
        self.assertEqual(self.git("rev-parse", "development-2"), initial)

    def test_local_default_diverged_stops(self):
        self.initialize()
        self.advance_remote()
        self.git("switch", "development-2")
        self.git("commit", "--allow-empty", "-m", "local advance")
        self.git("switch", "existing-work")
        result = self.launch("feat/test")
        self.assert_not_launched(result)
        self.assertIn("ahead/diverged", result.stderr)

    def test_tracked_local_state_stops(self):
        self.initialize()
        state = self.repo / ".workmux-local"
        state.mkdir()
        (state / "integration.md").write_text("must stay local")
        self.git("add", ".workmux-local")
        self.git("commit", "-m", "tracked state")
        result = self.launch("feat/test")
        self.assert_not_launched(result)
        self.assertIn("tracked files", result.stderr)

    def test_local_ignore_override_stops(self):
        self.initialize()
        (self.repo / ".gitignore").write_text("!/.workmux-local/\n!/.workmux-local/**\n")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "ignore override")
        result = self.launch("feat/test")
        self.assert_not_launched(result)
        self.assertIn("ignore rules", result.stderr)

    def test_default_branch_cannot_be_integration_branch(self):
        self.initialize()
        self.git("branch", "-D", "development-2")
        self.assert_not_launched(self.launch("development-2"))

    def test_missing_config_stops_before_fetch(self):
        self.initialize()
        before = self.git("rev-parse", "refs/remotes/origin/development-2")
        self.advance_remote()
        self.assert_not_launched(self.launch("--config", "missing.yaml", "feat/test"))
        self.assertEqual(self.git("rev-parse", "refs/remotes/origin/development-2"), before)

    def test_dirty_checkout_stops(self):
        self.initialize()
        (self.repo / "untracked.txt").write_text("user work")
        self.assert_not_launched(self.launch("feat/test"))

    def test_existing_local_branch_stops(self):
        self.initialize()
        self.git("branch", "feat/test")
        self.assert_not_launched(self.launch("feat/test"))

    def test_existing_remote_branch_stops(self):
        self.initialize()
        self.git("push", "origin", "HEAD:refs/heads/feat/test")
        self.assert_not_launched(self.launch("feat/test"))

    def test_github_failure_stops_without_guessing(self):
        self.initialize()
        self.env["TEST_GH_FAIL"] = "1"
        self.assert_not_launched(self.launch("feat/test"))

    def test_invalid_or_missing_default_stops(self):
        self.initialize()
        for value in ("", "null", "bad name", "main\nmaster"):
            with self.subTest(value=value):
                self.env["TEST_DEFAULT"] = value
                self.assert_not_launched(self.launch("feat/test"))

    def test_partial_creation_retains_recovery_context(self):
        self.initialize()
        self.env["TEST_WORKMUX_EXIT"] = "1"
        first = self.launch("feat/test")
        self.assertNotEqual(first.returncode, 0)
        record = json.loads(self.log.read_text())
        self.assertTrue(Path(record["prompt_path"]).is_file())
        self.log.unlink()
        self.assert_not_launched(self.launch("feat/test"))
        self.assertIn("feat/test", self.git("worktree", "list"))


if __name__ == "__main__":
    unittest.main()
