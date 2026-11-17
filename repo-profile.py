#!/usr/bin/env python3
"""Provision repository worktrees and explicitly start their local application."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def emit(**fields):
    # A flat TOON object; JSON quoting also escapes newlines in errors/paths.
    for key, value in fields.items():
        print(f"{key}: {json.dumps(value)}", flush=True)


def git(path, *args):
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Select an existing Git worktree with --worktree or --source.")
    return result.stdout.strip()


def checked_path(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Profile path escapes the repository: {relative}")
    return path


def load_profile(name):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
        raise ValueError("Profile names may contain letters, numbers, underscores and hyphens.")
    path = ROOT / "profiles" / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"Profile not found: {path}")
    return json.loads(path.read_text())


def run(command, worktree, env):
    # Application/install output is diagnostic; stdout stays machine readable.
    result = subprocess.run(command, cwd=worktree, env=env, stdout=sys.stderr)
    if result.returncode:
        raise ValueError(f"Command failed ({result.returncode}): {shlex.join(command)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Examples: repo-profile.py setup gary-ql --worktree . --install; "
        "repo-profile.py start gary-ql --worktree .; "
        "repo-profile.py render gary-ql"))
    parser.add_argument("action", choices=["setup", "check", "start", "render"])
    parser.add_argument("profile")
    parser.add_argument("--worktree", default=os.getcwd(), help="Target worktree (default: current directory)")
    parser.add_argument("--source", help="Configuration source (default: repository's main worktree)")
    parser.add_argument("--install", action="store_true", help="Run dependency install during setup")
    args = parser.parse_args()
    if args.install and args.action != "setup":
        parser.error("--install is only valid with setup")
    profile = load_profile(args.profile)
    if args.action == "render":
        config = profile["workmux"]
        command = shlex.join([sys.executable, str(Path(__file__).resolve()), "setup", args.profile])
        config["post_create"] = [command + ' --source "$WM_PROJECT_ROOT" --worktree "$WM_WORKTREE_PATH"']
        # JSON is a YAML subset, accepted by workmux; no YAML dependency required.
        print(json.dumps(config, indent=2))
        return

    worktree = Path(git(Path(args.worktree).resolve(), "rev-parse", "--show-toplevel"))
    if args.action == "setup":
        source = Path(args.source).resolve() if args.source else Path(
            git(worktree, "worktree", "list", "--porcelain").splitlines()[0].removeprefix("worktree "))
        common = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir"))
        if Path(git(source, "rev-parse", "--path-format=absolute", "--git-common-dir")) != common:
            raise ValueError("Source and destination must belong to the same repository.")
        # Validate every file before copying anything. Never overwrite local edits.
        pending = []
        for relative in profile.get("copy", []):
            target = checked_path(worktree, relative)
            if git(worktree, "ls-files", "--", relative):
                raise ValueError(f"Refusing to provision tracked configuration: {relative}")
            ignored = subprocess.run(["git", "-C", str(worktree), "check-ignore", "--quiet", "--", relative])
            if ignored.returncode:
                raise ValueError(f"Configuration must be ignored before provisioning: {relative}")
            if target.is_file():
                continue
            original = checked_path(source, relative)
            if not original.is_file():
                raise ValueError(f"Missing source configuration: {relative}; provision it in --source first.")
            pending.append((original, target))
        for original, target in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive create also preserves a destination created concurrently.
            with target.open("xb") as output, original.open("rb") as input_file:
                os.chmod(target, 0o600)
                shutil.copyfileobj(input_file, output)
        if args.install:
            run(profile["install"], worktree, os.environ.copy())
        emit(status="ready", copied=len(pending), dependencies="installed" if args.install else "unchanged")
        return

    for relative in profile.get("copy", []) + profile.get("dependency_paths", []):
        if not checked_path(worktree, relative).exists():
            raise ValueError(f"Missing {relative}; run setup {args.profile} --worktree {worktree} --install.")
    env = {**os.environ, **profile.get("environment", {})}
    for service in profile.get("services", []):
        result = subprocess.run(service["check"], cwd=worktree, env=env, capture_output=True, timeout=15)
        if result.returncode:
            raise ValueError(f"Shared service {service['name']} is unavailable; start it from the original checkout and retry.")
    port_config = profile.get("port")
    if port_config:
        port = int(env.get(port_config["environment"], port_config["default"]))
        with socket.socket() as probe:
            try:
                probe.bind(("", port))
            except OSError:
                raise ValueError(f"Port {port} is in use; stop the existing app or set {port_config['environment']} to a free port.")
    if args.action == "check":
        emit(status="ready", profile=args.profile)
        return
    if profile.get("prestart"):
        run(profile["prestart"], worktree, env)
    emit(status="starting", profile=args.profile)
    os.chdir(worktree)
    os.execvpe(profile["start"][0], profile["start"], env)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        emit(error=str(error))
        sys.exit(1)
