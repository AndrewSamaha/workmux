"""Exercise provisioning and startup without credentials, Docker or live services."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="profile tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "source"
        self.target = self.root / "worktree"
        self.tool = self.root / "workflow"
        self.tool.mkdir()
        (self.tool / "profiles").mkdir()
        shutil.copy(ROOT / "repo-profile.py", self.tool)
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        self.command("git", "init", str(self.repo))
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        (self.repo / ".gitignore").write_text("local.json\nnode_modules/\n")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "initial")
        self.git("worktree", "add", "-b", "task", str(self.target))
        (self.repo / "local.json").write_text("private configuration")
        self.marker = self.root / "started"
        self.profile = {
            "copy": ["local.json"], "dependency_paths": [],
            "environment": {"NODE_ENV": "local"},
            "services": [{"name": "redis", "check": [sys.executable, "-c", "pass"]}],
            "prestart": [sys.executable, "-c", "pass"],
            "start": [sys.executable, "-c", "import os,pathlib; pathlib.Path(" + repr(str(self.marker)) + ").write_text(os.environ['NODE_ENV'])"],
            "workmux": {"agent": "codex"},
        }
        self.save()

    def command(self, *args):
        return subprocess.run(args, capture_output=True, text=True, env=self.env, check=True)

    def git(self, *args):
        return self.command("git", "-C", str(self.repo), *args).stdout.strip()

    def save(self):
        (self.tool / "profiles" / "test.json").write_text(json.dumps(self.profile))

    def run_profile(self, action, *args):
        return subprocess.run([sys.executable, str(self.tool / "repo-profile.py"), action, "test",
                               "--worktree", str(self.target), *args],
                              capture_output=True, text=True, env=self.env)

    def test_copy_preserves_existing_config_and_git_is_clean(self):
        first = self.run_profile("setup")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual((self.target / "local.json").read_text(), "private configuration")
        self.assertEqual((self.target / "local.json").stat().st_mode & 0o777, 0o600)
        (self.target / "local.json").write_text("worktree override")
        (self.target / "local.json").chmod(0o640)
        second = self.run_profile("setup")
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertIn("copied: 0", second.stdout)
        self.assertEqual((self.target / "local.json").read_text(), "worktree override")
        self.assertEqual((self.target / "local.json").stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertNotIn("private configuration", first.stdout)

    def test_missing_source_and_nonignored_destinations_fail(self):
        (self.repo / "local.json").unlink()
        result = self.run_profile("setup")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing source configuration", result.stdout)
        self.profile["copy"] = ["not-ignored.json"]
        self.save()
        self.assertIn("must be ignored", self.run_profile("setup").stdout)

    def test_path_escape_and_wrong_repository_fail(self):
        self.profile["copy"] = ["../outside"]
        self.save()
        self.assertIn("escapes", self.run_profile("setup").stdout)
        other = self.root / "other"
        self.command("git", "init", str(other))
        self.assertIn("same repository", self.run_profile("setup", "--source", str(other)).stdout)

    def test_start_runs_profile_command_with_local_environment(self):
        self.run_profile("setup")
        result = self.run_profile("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.marker.read_text(), "local")

    def test_start_without_prestart_uses_profile_environment(self):
        self.run_profile("setup")
        del self.profile["prestart"]
        self.profile["environment"] = {"NODE_ENV": "qa"}
        self.save()
        result = self.run_profile("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.marker.read_text(), "qa")

    def test_prestart_failure_prevents_start(self):
        self.run_profile("setup")
        self.profile["prestart"] = [sys.executable, "-c", "raise SystemExit(1)"]
        self.save()
        result = self.run_profile("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Command failed", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_service_failure_prevents_start(self):
        self.run_profile("setup")
        self.profile["services"][0]["check"] = [sys.executable, "-c", "raise SystemExit(1)"]
        self.save()
        result = self.run_profile("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("redis is unavailable", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_command_center_install_and_start_use_recipe_and_port_override(self):
        self.profile = json.loads((ROOT / "profiles/command-center.json").read_text())
        self.save()
        relative = self.profile["copy"][0]
        original = self.repo / relative
        original.parent.mkdir(parents=True)
        original.write_text("private local override")
        for relative in self.profile["dependency_paths"]:
            dependency = self.target / relative
            dependency.parent.mkdir(parents=True, exist_ok=True)
            dependency.touch()
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        npm = fake_bin / "npm"
        npm.write_text("#!" + sys.executable + "\n"
                       "import json,os,pathlib,sys\n"
                       "p=pathlib.Path(" + repr(str(self.marker)) + ")\n"
                       "with p.open('a') as f: f.write(json.dumps([sys.argv[1:],os.getenv('NODE_ENV'),os.getenv('PORT')])+'\\n')\n")
        npm.chmod(0o755)
        self.env["PATH"] = str(fake_bin) + os.pathsep + self.env["PATH"]
        result = self.run_profile("setup", "--install")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.marker.read_text().splitlines()[0])[0],
                         ["ci", "--legacy-peer-deps"])
        self.assertEqual((self.target / self.profile["copy"][0]).read_text(), "private local override")
        with socket.socket() as listener:
            listener.bind(("", 0))
            self.env["PORT"] = str(listener.getsockname()[1])
            blocked = self.run_profile("start")
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("is in use", blocked.stdout)
            self.assertEqual(len(self.marker.read_text().splitlines()), 1)
        result = self.run_profile("start")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.marker.read_text().splitlines()[1]),
                         [["start"], "qa-gcp", self.env["PORT"]])
        self.assertEqual(self.profile["port"], {"environment": "PORT", "default": 3001})
        self.assertNotIn("prestart", self.profile)

    def test_render_uses_absolute_tool_and_quoted_workmux_variables(self):
        result = self.run_profile("render")
        config = json.loads(result.stdout)
        self.assertIn(str(self.tool / "repo-profile.py"), config["post_create"][0])
        self.assertIn('"$WM_WORKTREE_PATH"', config["post_create"][0])


if __name__ == "__main__":
    unittest.main()
